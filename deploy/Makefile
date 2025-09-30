.PHONY: help build ping web rtmp all

help:
	@echo "Available deploy targets:"
	@echo "  make build       - Build the deployment container"
	@echo "  make ping        - Test connectivity to the server"
	@echo "  make web         - Deploy web server (nginx) to Raspberry Pi"
	@echo "  make rtmp        - Deploy RTMP server (nginx-rtmp) to Raspberry Pi"
	@echo "  make all         - Deploy both web and RTMP servers"

build:
	docker build --tag sparrow_cam_deploy ./

ping:
	docker-compose run --rm deploy ansible all -m ping -i inventory.yml

web:
	docker-compose run --rm deploy ansible-playbook -i inventory.yml web.yml

rtmp:
	docker-compose run --rm deploy ansible-playbook -i inventory.yml rtmp.yml

all: web rtmp
	@echo "✅ Both web server and RTMP server deployed successfully"
