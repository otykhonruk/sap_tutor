IMAGE=sap-tutor
SIGNAL_USER=+380631764721
SIGNAL_CMD=docker run -it --platform=linux/amd64 -v signal-cli-state:/root/.local/share/signal-cli $(IMAGE) signal-cli -a $(SIGNAL_USER)
PLATFORM=--platform=linux/amd64

build:
	docker build -v signal-cli-state:/root/.local/share/signal-cli $(PLATFORM) $(IMAGE)

run:
	docker run -it -v signal-cli-state:/root/.local/share/signal-cli $(PLATFORM) $(IMAGE)

register:
	$(SIGNAL_CMD) register
