.PHONY: help build ping

help:
	@echo "Available deploy targets:"
	@echo "  make build  - Build the deployment container"
	@echo "  make ping   - Test connectivity to the server"

build:
	docker build --tag sparrow_cam_deploy ./

ping:
	docker-compose run --rm deploy ansible all -m ping -i inventory.yml
