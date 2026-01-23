.PHONY: help build ping setup_users setup_web setup_processor setup_storage run_archive_stream all

help:
	@echo "Available infrastructure targets:"
	@echo "  make build              - Build the infrastructure container"
	@echo "  make ping               - Test connectivity to the server"
	@echo "  make setup_users        - Setup users and groups"
	@echo "  make setup_storage      - Mount external hard drive"
	@echo "    DEVICE=<path>         - Override device path (default: /dev/sda1)"
	@echo "  make setup_processor    - Deploy processor service"
	@echo "  make setup_web          - Deploy web server (nginx)"
	@echo "  make setup_all          - Deploy all services (setup_users, setup_storage, setup_processor, setup_web)"
	@echo "  make run_archive_stream - Run archive stream script"
	@echo "    LIMIT=<number>        - Limit the number of segments to archive (default: 15)"

build:
	docker build --tag sparrow_cam_infra ./

ping:
	docker-compose run --rm infra ansible all -m ping -i inventory.yml

setup_users:
	docker-compose run --rm infra ansible-playbook -i inventory.yml setup_users.yml

setup_storage:
	docker-compose run --rm infra ansible-playbook -i inventory.yml setup_storage.yml $(if $(DEVICE),-e "device_to_mount=$(DEVICE)",)

setup_processor:
	docker-compose run --rm infra ansible-playbook -i inventory.yml setup_processor.yml

setup_web:
	docker-compose run --rm infra ansible-playbook -i inventory.yml setup_web.yml

setup_all: setup_users setup_storage setup_processor setup_web
	@echo "Users, hard drive, processor service, and web server deployed successfully"

archive:
	docker-compose run --rm infra ansible-playbook -i inventory.yml archive.yml $(if $(LIMIT),-e "limit=$(LIMIT)",)
