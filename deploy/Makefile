.PHONY: help build ping web rtmp processor all clean

help:
	@echo "Available deploy targets:"
	@echo "  make build       - Build the deployment container"
	@echo "  make ping        - Test connectivity to the server"
	@echo "  make web         - Deploy web server (nginx) to Raspberry Pi"
	@echo "  make rtmp        - Deploy RTMP server (nginx-rtmp) to Raspberry Pi"
	@echo "  make processor   - Deploy processor service with isolated Python environment"
	@echo "  make all         - Deploy web, RTMP, and processor services"
	@echo "  make clean       - Clean streaming data and annotations"

build:
	docker build --tag sparrow_cam_deploy ./

ping:
	docker-compose run --rm deploy ansible all -m ping -i inventory.yml

web:
	docker-compose run --rm deploy ansible-playbook -i inventory.yml web.yml

rtmp:
	docker-compose run --rm deploy ansible-playbook -i inventory.yml rtmp.yml

processor:
	docker-compose run --rm deploy ansible-playbook -i inventory.yml processor.yml

all: web rtmp processor
	@echo "✅ Web server, RTMP server, and processor service deployed successfully"

clean:
	docker-compose run --rm deploy ansible-playbook -i inventory.yml clean.yml
