.PHONY: help build start stream stop format check test e2e lab-build lab-run lab-format lab-check lab-test

help:
	@echo "SparrowCam Local Development"
	@echo ""
	@echo "Available commands:"
	@echo "  make build                 - Build the Docker image"
	@echo "  make start                 - Start the application (web on :8080)"
	@echo "    OPENCV_LOGS=1            - Start with OpenCV debug logging enabled"
	@echo "  make stream                - Stream sample.mp4 continuously (loops forever)"
	@echo "  make stop                  - Stop the application"
	@echo "  make format                - Format code with black and ruff"
	@echo "  make check                 - Run lint, type and security checks (no formatting)"
	@echo "  make test                  - Run unit tests for processor package"
	@echo "  make e2e                   - Run end-to-end integration tests"
	@echo "  make lab-build             - Build the lab Docker image"
	@echo "  make lab-run               - Launch lab GUI (files auto-update)"
	@echo "  make lab-format            - Format lab code with black and ruff"
	@echo "  make lab-check             - Run lint, type and security checks for lab"
	@echo "  make lab-test              - Run unit tests for lab package"

build:
	docker compose build

start:
	@if [ "$(OPENCV_LOGS)" = "1" ]; then \
		echo "Starting with OpenCV debug logging enabled..."; \
		OPENCV_LOG_LEVEL=DEBUG OPENCV_VIDEOIO_DEBUG=1 docker compose up -d; \
	else \
		docker compose up -d; \
	fi
	@echo ""
	@echo "SparrowCam is running!"
	@echo "  Web interface: http://localhost:8080"

stream:
	docker compose exec processor ffmpeg \
		-stream_loop -1 \
		-re \
		-i /app/sample.mp4 \
		-c:v libx264 \
		-preset ultrafast \
		-tune zerolatency \
		-g 24 \
		-pix_fmt yuv420p \
		-an \
		-f hls \
		-hls_time 1 \
		-hls_list_size 60 \
		-hls_flags delete_segments+append_list \
		-hls_segment_filename "/var/www/html/hls/sparrow_cam-%d.ts" \
		/var/www/html/hls/sparrow_cam.m3u8

stop:
	docker compose down

format:
	docker compose run --rm --no-deps processor bash -lc "\
		black processor tests && \
		printf '\033[32mBlack formatting complete\033[0m\n' && \
		ruff check --fix && \
		printf '\033[32mRuff formatting complete\033[0m\n'"

check:
	docker compose run --rm --no-deps processor bash -lc "\
		ruff check && \
		printf '\033[32mRuff check passed\033[0m\n' && \
		PYRIGHT_PYTHON_PATH=\$(which python3) pyright && \
		printf '\033[32mPyright check passed\033[0m\n' && \
		bandit -r processor && \
		printf '\033[32mBandit check passed\033[0m\n'"

test:
	docker compose run --rm --no-deps processor pytest --cov --cov-report=term --cov-report=term-missing

e2e:
	@bash e2e-test.sh


lab-build:
	docker compose -f docker-compose.lab.yml build

lab-run:
	docker compose -f docker-compose.lab.yml run --rm lab

lab-format:
	docker compose -f docker-compose.lab.yml run --rm --no-deps lab bash -lc "\
		black lab tests && \
		printf '\033[32mBlack formatting complete\033[0m\n' && \
		ruff check --fix && \
		printf '\033[32mRuff formatting complete\033[0m\n'"

lab-check:
	docker compose -f docker-compose.lab.yml run --rm --no-deps lab bash -lc "\
		ruff check && \
		printf '\033[32mRuff check passed\033[0m\n' && \
		PYRIGHT_PYTHON_PATH=\$(which python3) pyright && \
		printf '\033[32mPyright check passed\033[0m\n' && \
		bandit -r lab && \
		printf '\033[32mBandit check passed\033[0m\n'"

lab-test:
	docker compose -f docker-compose.lab.yml run --rm --no-deps lab pytest --cov --cov-report=term --cov-report=term-missing
