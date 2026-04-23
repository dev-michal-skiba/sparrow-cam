.PHONY: help build ping setup_users setup_web setup_processor setup_archive_api setup_storage setup_stream run_archive_stream all web_build check_git_state

help:
	@echo "Available infrastructure targets:"
	@echo "  make build                - Build the infrastructure container"
	@echo "  make ping                 - Test connectivity to the server"
	@echo "  make setup_users          - Setup users and groups"
	@echo "  make setup_storage        - Mount external hard drive"
	@echo "    DEVICE=<path>           - Override device path (default: /dev/sda1)"
	@echo "  make setup_processor      - Deploy processor service"
	@echo "  make setup_archive_api    - Deploy archive API service"
	@echo "  make setup_stream         - Deploy stream service"
	@echo "  make setup_web            - Build web app and deploy web server (nginx)"
	@echo "  make setup_all            - Deploy all services"
	@echo "  make run_archive_stream   - Run archive stream script"
	@echo "    LIMIT=<number>          - Limit the number of segments to archive (default: 15)"

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

setup_archive_api:
	docker-compose run --rm infra ansible-playbook -i inventory.yml setup_archive_api.yml

setup_stream:
	docker-compose run --rm infra ansible-playbook -i inventory.yml setup_stream.yml

check_git_state:
	@branch=$$(git rev-parse --abbrev-ref HEAD); \
	if [ "$$branch" != "master" ]; then \
		echo "ERROR: Not on master branch (currently on '$$branch'). Switch to master before deploying."; \
		exit 1; \
	fi
	@if ! git diff --quiet HEAD; then \
		echo "ERROR: Working tree has uncommitted changes. Commit or stash them before deploying."; \
		exit 1; \
	fi
	@git fetch origin
	@local=$$(git rev-parse HEAD); \
	remote=$$(git rev-parse origin/master); \
	if [ "$$local" != "$$remote" ]; then \
		echo "ERROR: Local master is not in sync with origin/master. Push or pull before deploying."; \
		exit 1; \
	fi

web_build:
	docker run --rm \
		-v $(shell pwd)/../app/web:/app/web \
		-w /app/web \
		node:20-alpine \
		sh -c "npm install && npm run build"

setup_web: check_git_state web_build
	docker-compose run --rm infra ansible-playbook -i inventory.yml setup_web.yml

setup_all: setup_users setup_storage setup_processor setup_archive_api setup_stream setup_web
	@echo "Users, hard drive, processor service, archive API, stream service, and web server deployed successfully"

archive:
	docker-compose run --rm infra ansible-playbook -i inventory.yml archive.yml $(if $(LIMIT),-e "limit=$(LIMIT)",)
