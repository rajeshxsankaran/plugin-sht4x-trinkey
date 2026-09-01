## Model 

Claude Opus 5 High 

## Plugin Creation Prompt

Please write a plugin that reads data from a SHT41 sensor (https://www.adafruit.com/product/5912) that is attached through a USB Serial port - /dev/ttyACM0 

Here is what I get when I read from the port - 

```
# Adafruit SHT4x Trinkey Factory Test
# Found SHT4x sensor. Serial number 0x15750F3E
# Serial number, Temperature in *C, Relative Humidity %, Touch
359993150, 21.14, 12.77, 178
359993150, 21.11, 12.75, 178
359993150, 21.13, 12.78, 179
359993150, 21.13, 12.79, 178
359993150, 21.13, 12.78, 179
359993150, 21.11, 12.77, 178
359993150, 21.11, 12.71, 179
359993150, 21.10, 12.74, 179
359993150, 21.13, 12.76, 179
359993150, 21.16, 12.74, 178
359993150, 21.12, 12.74, 178
359993150, 21.13, 12.76, 178
359993150, 21.14, 12.75, 178
359993150, 21.15, 12.75, 178
359993150, 21.14, 12.69, 178
359993150, 21.12, 12.76, 179
359993150, 21.17, 12.74, 178
```

Here is an example plugin - https://github.com/waggle-sensor/plugin-iio

and here is more info on how to create a plugin - https://sagecontinuum.org/docs/tutorials/edge-apps/creating-an-edge-app

Can you create all the files that I can put in a github repo and submit to ECR for containerization and deployment? 

## Job Submission Prompt

Great! I created a repo, submitted it to the portal and my app is built and ready for deployment - 

https://portal.sagecontinuum.org/apps/app/rajesh/sht4x-trinkey?tab=tags

Jobs on Waggle edge nodes are submitted using YAML files like this - 

```
name: W06A-reader-metone-es642
plugins:
- name: reader-metone-es642
  pluginSpec:
    image: registry.sagecontinuum.org/seanshahkarami/air-quality:0.3.0
    args:
    - --device
    - /host/dev/waggle-sensor-es642
    privileged: true
    selector:
      zone: core
    volume: {}
nodeTags: []
nodes:
  W06A: null
scienceRules:
- 'schedule("reader-metone-es642"): True'
successCriteria: []
```

Where W06A is the node on which the job has to run. 

Can you create a job to run the new plugin on node H013? Use default settings of publishing a value every 30 seconds.

## What happened? 

- Claude created the application and provided the following notes. I followed the nodes to add an icon and then submitted it into ECR. ECR build was successful. 
```
Full repo above. A few design notes worth flagging:

Continuous read, interval publish. The firmware streams as fast as it can, so the plugin reads the port continuously and publishes the mean (or median/last) over --publish-interval. A publish never blocks on the device, and the per-sample noise averages out. The samples metadata field tells downstream users how many readings backed each value, which doubles as a link-health signal.

Verified end to end. I ran it against real pywaggle in replay mode; data.ndjson came out clean, and the 12 unit tests pass. make replay reproduces that with no hardware.

Device stability. /dev/ttyACM0 is not stable across re-enumeration. There's a reconnect loop plus a --stale-timeout watchdog, and --autodetect matches on Adafruit's VID 0x239A plus a product-string hint. I deliberately did not hardcode a product ID — that varies with firmware build, so check yours with udevadm info -a -n /dev/ttyACM0 before writing the udev rule in the README. Also note --device alone is enough for Docker; this doesn't need privileged: true the way plugin-iio does.

Three things to settle before you submit:

- ecr-meta/ still needs ecr-icon.jpg (512×512) and ecr-science-image.jpg (≥1920×1080) — ECR expects both.
- env.temperature and env.relative_humidity are standard ontology names, but env.touch.raw isn't. Either register it or rename via --name-touch.
- If a node already runs another env sensor, the two will collide on those names. Override the names per deployment or lean on the sensor: sht4x metadata at query time.

The sage.yaml source.url and homepage point at a waggle-sensor/plugin-sht4x-trinkey path that doesn't exist yet — swap those for wherever you actually push.
```
- Claude created the submission script, but it made a simple mistake in the image registry link, I corrected it and the job scheduled and ran successfully. 

```
Submit with:

sh
sesctl submit --file-path H013-sht4x-trinkey.yaml

Two things I changed from what you might expect:

/host/dev/ttyACM0, not /dev/ttyACM0. Your es642 example uses the /host/dev/ prefix — that's the host device tree as seen from inside a privileged plugin container. Same applies here, so privileged: true is set. This overrides the plugin's /dev/ttyACM0 default, which is only right for local testing outside a container.

No --publish-interval. 30 seconds is the plugin default, so leaving it off gets you what you asked for. Add it explicitly if you'd rather have the job spec self-documenting.

Worth confirming before you submit:

The tag. I used 0.1.0 from your sage.yaml. Check the tags page for what actually built.
ttyACM0 is not a stable name. If the node has any other USB serial device, enumeration order decides who gets ttyACM0 and a reboot can swap them. Your es642 job uses waggle-sensor-es642, which is a udev symlink — that's the right pattern here too. If Hawaii nodes carry a udev rule for the Trinkey, use that symlink instead. If not, --autodetect in place of --device is a decent stopgap since it matches on Adafruit's VID.
zone: core assumes the Trinkey is plugged into the core node. Change to zone: shield if it's on the shield.

Once it's running, env.temperature filtered on meta.sensor == "sht4x" and vsn == "H013" should show up in the data portal within a minute or two.
```

- YAML Produced by Claude 

```
name: H013-sht4x-trinkey
plugins:
- name: sht4x-trinkey
  pluginSpec:
    image: registry.sagecontinuum.org/rajesh/sht4x-trinkey:0.1.0
    args:
    - --device
    - /host/dev/ttyACM0
    privileged: true
    selector:
      zone: core
    volume: {}
nodeTags: []
nodes:
  H013: null
scienceRules:
- 'schedule("sht4x-trinkey"): True'
successCriteria: []
```

- Example output:
```
{"timestamp":"2026-09-01T23:36:05.556951326Z","name":"env.relative_humidity","value":13.466,"meta":{"aggregate":"mean","device":"/host/dev/ttyACM0","host":"00004cbb4713c685.agx-thor","node":"00004cbb4713c685","plugin":"registry.sagecontinuum.org/rajesh/sht4x-trinkey:0.1","samples":"29","sensor":"sht4x","sensor_serial":"0x15750F3E","task":"sht4x-trinkey","vsn":"H013","zone":"core"}}
{"timestamp":"2026-09-01T23:36:35.930746849Z","name":"env.relative_humidity","value":13.465,"meta":{"aggregate":"mean","device":"/host/dev/ttyACM0","host":"00004cbb4713c685.agx-thor","node":"00004cbb4713c685","plugin":"registry.sagecontinuum.org/rajesh/sht4x-trinkey:0.1","samples":"29","sensor":"sht4x","sensor_serial":"0x15750F3E","task":"sht4x-trinkey","vsn":"H013","zone":"core"}}
{"timestamp":"2026-09-01T23:37:06.304049572Z","name":"env.relative_humidity","value":13.46,"meta":{"aggregate":"mean","device":"/host/dev/ttyACM0","host":"00004cbb4713c685.agx-thor","node":"00004cbb4713c685","plugin":"registry.sagecontinuum.org/rajesh/sht4x-trinkey:0.1","samples":"29","sensor":"sht4x","sensor_serial":"0x15750F3E","task":"sht4x-trinkey","vsn":"H013","zone":"core"}}
{"timestamp":"2026-09-01T23:37:36.6775752Z","name":"env.relative_humidity","value":13.455,"meta":{"aggregate":"mean","device":"/host/dev/ttyACM0","host":"00004cbb4713c685.agx-thor","node":"00004cbb4713c685","plugin":"registry.sagecontinuum.org/rajesh/sht4x-trinkey:0.1","samples":"29","sensor":"sht4x","sensor_serial":"0x15750F3E","task":"sht4x-trinkey","vsn":"H013","zone":"core"}}
{"timestamp":"2026-09-01T23:36:05.556951326Z","name":"env.temperature","value":26.931,"meta":{"aggregate":"mean","device":"/host/dev/ttyACM0","host":"00004cbb4713c685.agx-thor","node":"00004cbb4713c685","plugin":"registry.sagecontinuum.org/rajesh/sht4x-trinkey:0.1","samples":"29","sensor":"sht4x","sensor_serial":"0x15750F3E","task":"sht4x-trinkey","vsn":"H013","zone":"core"}}
{"timestamp":"2026-09-01T23:36:35.930746849Z","name":"env.temperature","value":26.938,"meta":{"aggregate":"mean","device":"/host/dev/ttyACM0","host":"00004cbb4713c685.agx-thor","node":"00004cbb4713c685","plugin":"registry.sagecontinuum.org/rajesh/sht4x-trinkey:0.1","samples":"29","sensor":"sht4x","sensor_serial":"0x15750F3E","task":"sht4x-trinkey","vsn":"H013","zone":"core"}}
{"timestamp":"2026-09-01T23:37:06.304049572Z","name":"env.temperature","value":26.974,"meta":{"aggregate":"mean","device":"/host/dev/ttyACM0","host":"00004cbb4713c685.agx-thor","node":"00004cbb4713c685","plugin":"registry.sagecontinuum.org/rajesh/sht4x-trinkey:0.1","samples":"29","sensor":"sht4x","sensor_serial":"0x15750F3E","task":"sht4x-trinkey","vsn":"H013","zone":"core"}}
{"timestamp":"2026-09-01T23:37:36.6775752Z","name":"env.temperature","value":26.982,"meta":{"aggregate":"mean","device":"/host/dev/ttyACM0","host":"00004cbb4713c685.agx-thor","node":"00004cbb4713c685","plugin":"registry.sagecontinuum.org/rajesh/sht4x-trinkey:0.1","samples":"29","sensor":"sht4x","sensor_serial":"0x15750F3E","task":"sht4x-trinkey","vsn":"H013","zone":"core"}}
{"timestamp":"2026-09-01T23:36:05.556951326Z","name":"env.touch.raw","value":178.5,"meta":{"aggregate":"mean","device":"/host/dev/ttyACM0","host":"00004cbb4713c685.agx-thor","node":"00004cbb4713c685","plugin":"registry.sagecontinuum.org/rajesh/sht4x-trinkey:0.1","samples":"29","sensor":"sht4x","sensor_serial":"0x15750F3E","task":"sht4x-trinkey","vsn":"H013","zone":"core"}}
{"timestamp":"2026-09-01T23:36:35.930746849Z","name":"env.touch.raw","value":178.4,"meta":{"aggregate":"mean","device":"/host/dev/ttyACM0","host":"00004cbb4713c685.agx-thor","node":"00004cbb4713c685","plugin":"registry.sagecontinuum.org/rajesh/sht4x-trinkey:0.1","samples":"29","sensor":"sht4x","sensor_serial":"0x15750F3E","task":"sht4x-trinkey","vsn":"H013","zone":"core"}}
{"timestamp":"2026-09-01T23:37:06.304049572Z","name":"env.touch.raw","value":178.6,"meta":{"aggregate":"mean","device":"/host/dev/ttyACM0","host":"00004cbb4713c685.agx-thor","node":"00004cbb4713c685","plugin":"registry.sagecontinuum.org/rajesh/sht4x-trinkey:0.1","samples":"29","sensor":"sht4x","sensor_serial":"0x15750F3E","task":"sht4x-trinkey","vsn":"H013","zone":"core"}}
{"timestamp":"2026-09-01T23:37:36.6775752Z","name":"env.touch.raw","value":178.4,"meta":{"aggregate":"mean","device":"/host/dev/ttyACM0","host":"00004cbb4713c685.agx-thor","node":"00004cbb4713c685","plugin":"registry.sagecontinuum.org/rajesh/sht4x-trinkey:0.1","samples":"29","sensor":"sht4x","sensor_serial":"0x15750F3E","task":"sht4x-trinkey","vsn":"H013","zone":"core"}}
```
