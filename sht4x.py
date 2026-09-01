"""
Parsing helpers for the Adafruit SHT4x Trinkey factory-test firmware stream.

The firmware emits a banner followed by comma separated readings on the USB
CDC ACM port:

    # Adafruit SHT4x Trinkey Factory Test
    # Found SHT4x sensor. Serial number 0x15750F3E
    # Serial number, Temperature in *C, Relative Humidity %, Touch
    359993150, 21.14, 12.77, 178

Lines beginning with '#' are informational. Data lines carry the sensor's
32 bit serial number (decimal), temperature in degrees Celsius, relative
humidity in percent and a raw capacitive touch count.

This module is intentionally free of pywaggle and pyserial imports so it can
be unit tested anywhere.
"""

import re
from dataclasses import dataclass
from typing import Optional

# Plausibility limits. The SHT4x datasheet range is -40..125 C and 0..100 %RH;
# the bounds below are deliberately a little wider so that a genuinely odd but
# real reading is published rather than silently dropped.
TEMPERATURE_MIN_C = -50.0
TEMPERATURE_MAX_C = 130.0
HUMIDITY_MIN_PCT = -5.0
HUMIDITY_MAX_PCT = 110.0
TOUCH_MIN = 0
TOUCH_MAX = 65535

_BANNER_SERIAL_RE = re.compile(r"serial\s+number\s+0x([0-9a-f]+)", re.IGNORECASE)


class ParseError(ValueError):
    """Raised when a non-comment line cannot be interpreted as a reading."""


@dataclass(frozen=True)
class Sample:
    serial_number: int
    temperature: float
    humidity: float
    touch: int

    @property
    def serial_hex(self) -> str:
        return f"0x{self.serial_number:08X}"


def parse_banner_serial(line: str) -> Optional[int]:
    """Return the serial number from a banner line, or None if absent.

    >>> parse_banner_serial("# Found SHT4x sensor. Serial number 0x15750F3E")
    359993150
    """
    match = _BANNER_SERIAL_RE.search(line)
    if match is None:
        return None
    return int(match.group(1), 16)


def parse_line(line: str) -> Optional[Sample]:
    """Parse one line of the stream.

    Returns a Sample for a data line, or None for blank lines and comments.
    Raises ParseError if the line looks like data but cannot be decoded.
    """
    line = line.strip()

    if not line or line.startswith("#"):
        return None

    fields = [field.strip() for field in line.split(",")]
    if len(fields) != 4:
        raise ParseError(f"expected 4 comma separated fields, got {len(fields)}: {line!r}")

    try:
        serial_number = int(fields[0])
        temperature = float(fields[1])
        humidity = float(fields[2])
        touch = int(float(fields[3]))
    except ValueError as exc:
        raise ParseError(f"could not convert fields in {line!r}: {exc}") from exc

    if not TEMPERATURE_MIN_C <= temperature <= TEMPERATURE_MAX_C:
        raise ParseError(f"temperature {temperature} out of range in {line!r}")
    if not HUMIDITY_MIN_PCT <= humidity <= HUMIDITY_MAX_PCT:
        raise ParseError(f"humidity {humidity} out of range in {line!r}")
    if not TOUCH_MIN <= touch <= TOUCH_MAX:
        raise ParseError(f"touch {touch} out of range in {line!r}")

    return Sample(
        serial_number=serial_number,
        temperature=temperature,
        humidity=humidity,
        touch=touch,
    )
