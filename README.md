# SHT4x Trinkey Plugin

Reads an [Adafruit SHT4x Trinkey](https://www.adafruit.com/product/5912) over USB serial and publishes temperature, relative humidity and the raw capacitive touch count to Waggle.

The Trinkey ships with factory-test firmware that enumerates as a USB CDC ACM device (usually `/dev/ttyACM0`) and streams comma separated readings:

```
# Adafruit SHT4x Trinkey Factory Test
# Found SHT4x sensor. Serial number 0x15750F3E
# Serial number, Temperature in *C, Relative Humidity %, Touch
359993150, 21.14, 12.77, 178
359993150, 21.11, 12.75, 178
```

The plugin reads that stream continuously, aggregates the samples over a publish interval and emits one measurement per name per interval. Reading continuously rather than sampling on demand means a publish never waits on the device and a stalled port is detected quickly.

## Measurements

| Name | Units | Notes |
| --- | --- | --- |
| `env.temperature` | degrees Celsius | |
| `env.relative_humidity` | percent | |
| `env.touch.raw` | counts | uncalibrated capacitive reading from the Trinkey pad |

With `--publish-extrema`, `.min` and `.max` variants of the temperature and humidity names are also published for each interval.

Every measurement carries metadata: `sensor` (`sht4x`), `sensor_serial` (the sensor's 32-bit serial in hex), `device`, `aggregate` and `samples` (how many raw readings went into the value).

If you deploy this alongside other environmental sensors on the same node, either give it distinct measurement names via `--name-temperature` / `--name-humidity` or rely on the `sensor` metadata field to disambiguate at query time.

## Arguments

| Flag | Default | Description |
| --- | --- | --- |
| `--device` | `/dev/ttyACM0` | Serial device to read |
| `--baudrate` | `115200` | Serial baud rate |
| `--autodetect` | off | Scan USB CDC ports for an Adafruit Trinkey instead of trusting `--device` |
| `--publish-interval` | `30` | Seconds between published measurements |
| `--aggregate` | `mean` | How to reduce an interval's samples: `mean`, `median` or `last` |
| `--publish-touch` / `--no-publish-touch` | on | Publish the raw touch count |
| `--publish-extrema` | off | Also publish per-interval min and max |
| `--name-temperature` | `env.temperature` | Measurement name override |
| `--name-humidity` | `env.relative_humidity` | Measurement name override |
| `--name-touch` | `env.touch.raw` | Measurement name override |
| `--read-timeout` | `2.0` | Serial read timeout in seconds |
| `--stale-timeout` | `60` | Reopen the port if no valid reading arrives in this many seconds |
| `--reconnect-delay` | `5.0` | Delay before reopening the port after an error |
| `--replay` | none | Read a text file instead of a serial port |
| `--replay-delay` | `0` | Seconds to sleep between replayed lines |
| `--debug` | off | Debug logging, including every parsed sample |

## Device handling

USB serial devices on a node re-enumerate — on reboot, on a power blip, or when another device claims `ttyACM0` first. The plugin handles this two ways:

- **Reconnect loop.** Any serial error, or a stretch of `--stale-timeout` seconds without a valid reading, closes the port and reopens it after `--reconnect-delay`.
- **`--autodetect`.** Scans for a CDC device with Adafruit's vendor ID (`0x239A`) whose product or description string mentions "trinkey" or "sht4x", falling back to `--device` when nothing matches.

For a permanent deployment, a udev rule giving the Trinkey a stable symlink is more robust than either:

```
# /etc/udev/rules.d/99-sht4x-trinkey.rules
SUBSYSTEM=="tty", ATTRS{idVendor}=="239a", SYMLINK+="sht4x-trinkey"
```

Then pass `--device /dev/sht4x-trinkey`. Confirm the vendor and product IDs on your unit with `lsusb` or `udevadm info -a -n /dev/ttyACM0` first; the product ID varies with the firmware build.

## Local development

```sh
pip3 install -r requirements.txt
```

Run against the real device:

```sh
export PYWAGGLE_LOG_DIR=test-run
python3 main.py --device /dev/ttyACM0 --publish-interval 10 --debug
```

Run against the captured sample stream with no hardware attached:

```sh
make replay
cat test-run/data.ndjson
```

Run the unit tests:

```sh
pytest -q
```

## Build and run the container

```sh
make build
docker run --rm --device /dev/ttyACM0 plugin-sht4x-trinkey:0.1.0 --device /dev/ttyACM0 --debug
```

Passing `--device` to Docker is sufficient; the plugin does not need `privileged: true`.

## Deploying

Test on a development node first (see [Testing an edge app](https://sagecontinuum.org/docs/tutorials/edge-apps/testing-an-edge-app)), then submit to ECR (see [Publishing to ECR](https://sagecontinuum.org/docs/tutorials/edge-apps/publishing-to-ecr)):

```sh
sudo pluginctl deploy --name sht4x --selector zone=core \
  registry.sagecontinuum.org/<username>/sht4x-trinkey:0.1.0 -- --debug
```

An example job spec is in `job.yaml`.

## Before you submit to ECR

- Add `ecr-meta/ecr-icon.jpg` (512x512) and `ecr-meta/ecr-science-image.jpg` (at least 1920x1080). ECR expects both; they are not in this repo.
- Fill in `authors`, `funding` and `license` in `sage.yaml`, and update `homepage` and `source.url` to your actual repo.
- Tag the release in git. ECR builds from a tag, so the version in the ECR submission form should match.
- Confirm `env.touch.raw` is registered in the Waggle ontology, or rename it. `env.temperature` and `env.relative_humidity` are already standard names.

## Notes on the firmware

The per-line serial number is the decimal form of the hex serial in the banner (`0x15750F3E` = `359993150`), so the two are cross-checked at runtime. If you reflash the Trinkey with CircuitPython or your own CircuitPython/Arduino sketch, keep the line format the same and this plugin will keep working; otherwise adjust `parse_line` in `sht4x.py` and its tests.
