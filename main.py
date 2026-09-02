#!/usr/bin/env python3
"""
Waggle edge app for the Adafruit SHT4x Trinkey (product 5912).

The Trinkey enumerates as a USB CDC ACM device (typically /dev/ttyACM0) and
streams temperature, relative humidity and a raw capacitive touch count. This
app reads that stream, aggregates it over a publish interval and publishes the
result to the node and Beehive.
"""

import argparse
import logging
import signal
import statistics
import sys
import time
from typing import List, Optional

import serial
from serial.tools import list_ports
from waggle.plugin import Plugin

from sht4x import ParseError, Sample, parse_banner_serial, parse_line

# Adafruit's USB vendor ID. The Trinkey's product ID varies by firmware build,
# so device matching is done on vendor ID plus product string.
ADAFRUIT_VENDOR_ID = 0x239A
DEVICE_NAME_HINTS = ("trinkey", "sht4x")

logger = logging.getLogger("sht4x-trinkey")

# Set by the SIGTERM/SIGINT handler so the read loop can unwind cleanly and
# flush any queued measurements.
_shutdown = False


def handle_signal(signum, _frame):
    global _shutdown
    logger.info("received signal %s, shutting down", signum)
    _shutdown = True


def find_device(preferred: str, autodetect: bool) -> str:
    """Return the serial device path to open.

    If autodetect is enabled, scan for an Adafruit CDC device and fall back to
    the preferred path when no match is found.
    """
    if not autodetect:
        return preferred

    for port in list_ports.comports():
        if port.vid != ADAFRUIT_VENDOR_ID:
            continue
        haystack = " ".join(
            str(field or "") for field in (port.product, port.description, port.manufacturer)
        ).lower()
        if any(hint in haystack for hint in DEVICE_NAME_HINTS):
            logger.info("autodetected %s (%s)", port.device, port.description)
            return port.device

    logger.warning("autodetect found no Adafruit Trinkey, falling back to %s", preferred)
    return preferred


class Aggregator:
    """Collects samples between publishes."""

    def __init__(self):
        self.samples: List[Sample] = []

    def add(self, sample: Sample) -> None:
        self.samples.append(sample)

    def clear(self) -> None:
        self.samples = []

    def __len__(self) -> int:
        return len(self.samples)

    def summarize(self, method: str) -> dict:
        temperatures = [s.temperature for s in self.samples]
        humidities = [s.humidity for s in self.samples]
        touches = [float(s.touch) for s in self.samples]

        if method == "mean":
            reduce = statistics.fmean
        elif method == "median":
            reduce = statistics.median
        else:  # last
            reduce = lambda values: values[-1]  # noqa: E731

        return {
            "temperature": reduce(temperatures),
            "relative_humidity": reduce(humidities),
            "touch": reduce(touches),
            "temperature_min": min(temperatures),
            "temperature_max": max(temperatures),
            "relative_humidity_min": min(humidities),
            "relative_humidity_max": max(humidities),
            "count": len(self.samples),
        }


def publish(plugin: Plugin, args, aggregator: Aggregator, serial_number: Optional[int]) -> None:
    if len(aggregator) == 0:
        logger.warning("no valid samples in the last %.1fs, nothing to publish", args.publish_interval)
        return

    summary = aggregator.summarize(args.aggregate)
    timestamp = time.time_ns()

    meta = {
        "sensor": "sht4x",
        "device": args.device,
        "aggregate": args.aggregate,
        "samples": str(summary["count"]),
    }
    if serial_number is not None:
        meta["sensor_serial"] = f"0x{serial_number:08X}"

    plugin.publish(args.name_temperature, round(summary["temperature"], 3), meta=meta, timestamp=timestamp)
    plugin.publish(args.name_humidity, round(summary["relative_humidity"], 3), meta=meta, timestamp=timestamp)

    if args.publish_touch:
        plugin.publish(args.name_touch, round(summary["touch"], 1), meta=meta, timestamp=timestamp)

    if args.publish_extrema:
        plugin.publish(f"{args.name_temperature}.min", round(summary["temperature_min"], 3), meta=meta, timestamp=timestamp)
        plugin.publish(f"{args.name_temperature}.max", round(summary["temperature_max"], 3), meta=meta, timestamp=timestamp)
        plugin.publish(f"{args.name_humidity}.min", round(summary["relative_humidity_min"], 3), meta=meta, timestamp=timestamp)
        plugin.publish(f"{args.name_humidity}.max", round(summary["relative_humidity_max"], 3), meta=meta, timestamp=timestamp)

    logger.info(
        "published T=%.2f C RH=%.2f %% touch=%.0f from %d samples",
        summary["temperature"],
        summary["relative_humidity"],
        summary["touch"],
        summary["count"],
    )
    aggregator.clear()


def consume_stream(stream, plugin: Plugin, args) -> None:
    """Read lines from an open stream until it ends or we are asked to stop.

    Works with both a pyserial handle and a plain file object, which is what
    makes --replay possible.
    """
    aggregator = Aggregator()
    serial_number: Optional[int] = None
    last_publish = time.monotonic()
    last_valid = time.monotonic()

    while not _shutdown:
        raw = stream.readline()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")

        if raw == "":
            # Replay files end here. On a live port readline() returns an empty
            # string on timeout, which is handled by the watchdog below.
            if args.replay:
                break
        else:
            banner_serial = parse_banner_serial(raw)
            if banner_serial is not None:
                serial_number = banner_serial
                logger.info("sensor serial number %s", f"0x{banner_serial:08X}")

            try:
                sample = parse_line(raw)
            except ParseError as exc:
                logger.debug("skipping line: %s", exc)
                sample = None

            if sample is not None:
                if serial_number is None:
                    serial_number = sample.serial_number
                aggregator.add(sample)
                last_valid = time.monotonic()
                if args.debug:
                    logger.debug(
                        "sample T=%.2f RH=%.2f touch=%d", sample.temperature, sample.humidity, sample.touch
                    )

        now = time.monotonic()

        if now - last_publish >= args.publish_interval:
            publish(plugin, args, aggregator, serial_number)
            last_publish = now

        if not args.replay and now - last_valid > args.stale_timeout:
            raise serial.SerialException(
                f"no valid readings for {args.stale_timeout}s, reopening {args.device}"
            )

        if args.replay and args.replay_delay > 0:
            time.sleep(args.replay_delay)

    # Flush whatever is left so a short replay or a clean shutdown still emits.
    if len(aggregator) > 0:
        publish(plugin, args, aggregator, serial_number)


def run(args) -> int:
    with Plugin() as plugin:
        if args.replay:
            logger.info("replaying %s instead of reading a serial port", args.replay)
            with open(args.replay, "r") as stream:
                consume_stream(stream, plugin, args)
            return 0

        while not _shutdown:
            args.device = find_device(args.device, args.autodetect)
            try:
                logger.info("opening %s at %d baud", args.device, args.baudrate)
                with serial.Serial(args.device, args.baudrate, timeout=args.read_timeout) as stream:
                    # The first line is usually a partial read from whatever was
                    # already in the device's buffer.
                    stream.reset_input_buffer()
                    stream.readline()
                    consume_stream(stream, plugin, args)
            except (serial.SerialException, OSError) as exc:
                if _shutdown:
                    break
                logger.error("serial error: %s", exc)
                logger.info("reconnecting in %.1fs", args.reconnect_delay)
                time.sleep(args.reconnect_delay)

    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Publish temperature, humidity and touch from an Adafruit SHT4x Trinkey.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--device", default="/dev/ttyACM0", help="serial device to read")
    parser.add_argument("--baudrate", type=int, default=115200, help="serial baud rate")
    parser.add_argument(
        "--autodetect",
        action="store_true",
        help="scan USB CDC ports for an Adafruit Trinkey instead of trusting --device",
    )
    parser.add_argument(
        "--publish-interval", type=float, default=30.0, help="seconds between published measurements"
    )
    parser.add_argument(
        "--aggregate",
        choices=("mean", "median", "last"),
        default="mean",
        help="how to reduce the samples collected during a publish interval",
    )
    parser.add_argument(
        "--publish-touch", action="store_true", default=True, help="publish the raw capacitive touch count"
    )
    parser.add_argument(
        "--no-publish-touch", dest="publish_touch", action="store_false", help="suppress the touch measurement"
    )
    parser.add_argument(
        "--publish-extrema",
        action="store_true",
        help="also publish per-interval min and max for temperature and humidity",
    )

    parser.add_argument("--name-temperature", default="env.temperature", help="measurement name for temperature")
    parser.add_argument(
        "--name-humidity", default="env.relative_humidity", help="measurement name for relative humidity"
    )
    parser.add_argument("--name-touch", default="env.touch.raw", help="measurement name for the touch count")

    parser.add_argument("--read-timeout", type=float, default=2.0, help="serial read timeout in seconds")
    parser.add_argument(
        "--stale-timeout",
        type=float,
        default=60.0,
        help="reopen the port if no valid reading arrives within this many seconds",
    )
    parser.add_argument("--reconnect-delay", type=float, default=5.0, help="delay before reopening the port")

    parser.add_argument("--replay", help="read from a text file instead of a serial port (for testing)")
    parser.add_argument(
        "--replay-delay", type=float, default=0.0, help="seconds to sleep between replayed lines"
    )

    parser.add_argument("--debug", action="store_true", help="enable debug logging")

    return parser.parse_args(argv)


def main():
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    sys.exit(run(args))


if __name__ == "__main__":
    main()
