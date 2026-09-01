# SHT4x Trinkey: Low-Cost Environmental Sensing at the Edge

## Science

Near-surface air temperature and relative humidity are foundational measurements for urban heat studies, microclimate characterization, agricultural monitoring and enclosure health tracking on instrumented nodes. Their value comes less from any single measurement than from density: a heat island gradient, a canopy-to-pavement contrast or a cold-air drainage pattern only becomes visible when many points are sampled at once.

Dense deployment requires sensors cheap enough to place in quantity and simple enough to attach without custom hardware. The Adafruit SHT4x Trinkey pairs a Sensirion SHT4x temperature and humidity sensor with a USB stem, so any node with a spare USB port becomes a measurement site with no wiring, no I2C bus arbitration and no additional power budget beyond what USB supplies.

## Sensor

The Sensirion SHT4x is a digital CMOSens temperature and humidity sensor with a typical accuracy of about ±1.8 %RH and ±0.2 °C over the normal ambient range, an operating range of -40 to 125 °C and 0 to 100 %RH, and low drift over multi-year deployments. The Trinkey carriers it on a USB-A board along with a capacitive touch pad, and the stock firmware streams readings over USB CDC serial.

Two caveats matter for siting. The board is not weatherproof, so outdoor use needs a radiation shield and moisture protection. And the USB stem places the sensor close to the host, so self-heating from the node enclosure will bias readings warm unless the Trinkey is extended away on a cable and shielded from the enclosure's thermal plume.

## What this application does

The plugin opens the Trinkey's serial port, continuously parses the streamed readings, and publishes an aggregate of each interval's samples as `env.temperature`, `env.relative_humidity` and `env.touch.raw`. Aggregating over an interval rather than sampling instantaneously suppresses the sensor's per-reading noise and yields a sample count that downstream users can use to weight or filter measurements.

The raw capacitive touch count is published as well. It is not a scientific measurement, but it tracks the dielectric environment around the board and is useful as a coarse indicator of condensation or physical contact with the sensor.

## Interpreting the data

Each measurement carries the sensor's hardware serial number in its metadata, which uniquely identifies the physical unit across redeployments and lets a suspect sensor be traced through the archive after the fact. The `samples` metadata field reports how many raw readings contributed to the published value; an unusually low count indicates a degraded serial link and those points should be treated with suspicion.

Temperature and humidity values are published as reported by the sensor, with no radiation, self-heating or siting correction applied. Users comparing across nodes should account for enclosure and mounting differences.

## References

- Sensirion SHT4x datasheet: https://sensirion.com/products/catalog/SHT40
- Adafruit SHT4x Trinkey product page: https://www.adafruit.com/product/5912
