CONTAINER_NAME=prometheus-ame
VERSION=v0.1a
PODMAN=$(shell type -P podman || type -P docker)

all: container

.PHONY: contaienr
container:
	$(PODMAN) build -t $(CONTAINER_NAME):$(VERSION) .
