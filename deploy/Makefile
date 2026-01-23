.PHONY: help build ping users web processor mount archive_stream all clean

help:
	@echo "Available deploy targets:"
	@echo "  make build           - Build the deployment container"
	@echo "  make ping            - Test connectivity to the server"
	@echo "  make users           - Setup users and groups"
	@echo "  make mount           - Mount external hard drive"
	@echo "    DEVICE=<path>      - Override device path (default: /dev/sda1)"
	@echo "  make processor       - Deploy processor service"
	@echo "  make web             - Deploy web server (nginx)"
	@echo "  make archive_stream  - Run archive stream script"
	@echo "    LIMIT=<number>     - Limit the number of segments to archive (default: 15)"
	@echo "  make all             - Deploy all services (users, mount, RTMP, processor, web)"
	@echo "  make clean           - Clean streaming data and annotations"

build:
	docker build --tag sparrow_cam_deploy ./

ping:
	docker-compose run --rm deploy ansible all -m ping -i inventory.yml

users:
	docker-compose run --rm deploy ansible-playbook -i inventory.yml users.yml

processor:
	docker-compose run --rm deploy ansible-playbook -i inventory.yml processor.yml

archive_stream:
	docker-compose run --rm deploy ansible-playbook -i inventory.yml archive_stream.yml $(if $(LIMIT),-e "limit=$(LIMIT)",)

web:
	docker-compose run --rm deploy ansible-playbook -i inventory.yml web.yml

mount:
	docker-compose run --rm deploy ansible-playbook -i inventory.yml mount.yml $(if $(DEVICE),-e "device_to_mount=$(DEVICE)",)

all: users mount processor web
	@echo "Users, hard drive, processor service, and web server deployed successfully"

clean:
	docker-compose run --rm deploy ansible-playbook -i inventory.yml clean.yml
