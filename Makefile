IMAGE ?= plugin-sht4x-trinkey
VERSION ?= 0.1.0
DEVICE ?= /dev/ttyACM0

.PHONY: test build run replay clean

test:
	pytest -q

build:
	docker build -t $(IMAGE):$(VERSION) .

# Run the built image against a real Trinkey. --device is enough; the plugin
# does not need full privileged mode.
run:
	docker run --rm --device $(DEVICE) $(IMAGE):$(VERSION) --device $(DEVICE) --debug

# Run against the captured sample stream, no hardware required.
replay:
	PYWAGGLE_LOG_DIR=test-run python3 main.py --replay test/sample_stream.txt --publish-interval 1 --debug

clean:
	rm -rf test-run __pycache__ .pytest_cache
