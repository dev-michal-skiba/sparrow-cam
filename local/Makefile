.PHONY: help build start stop clean format check test e2e

help:
	@echo "SparrowCam Local Development"
	@echo ""
	@echo "Available commands:"
	@echo "  make build                 - Build the Docker image"
	@echo "  make start                 - Start the application (web on :8080, RTMP on :8081)"
	@echo "    OPENCV_LOGS=1            - Start with OpenCV debug logging enabled"
	@echo "  make clean                 - Stop and remove containers, volumes, and generated files"
	@echo "  make stop                  - Stop the application"
	@echo "  make format                - Format code with black and ruff"
	@echo "  make check                 - Run lint, type and security checks (no formatting)"
	@echo "  make test                  - Run unit tests for processor package"
	@echo "  make e2e                   - Run end-to-end integration tests"
	@echo "  make lab-convert           - Convert archived .ts files to .png files"

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
	@echo "  RTMP endpoint: rtmp://localhost:8081/live/sparrow_cam"
	@echo ""
	@echo "To stream a video:"
	@echo "  ffmpeg -re -stream_loop -1 -i sample.mp4 -c copy -f flv rtmp://localhost:8081/live/sparrow_cam"

stop:
	docker compose down

clean:
	@echo "Cleaning HLS and annotations data volumes (containers stay up)..."
	@# Use a temporary container with the same volume mounts to clean data
	docker compose run --rm --entrypoint sh processor -c "\
		rm -rf /var/www/html/hls/* && \
		rm -rf /var/www/html/annotations/*"
	@echo "Cleanup completed successfully"
	@echo "- HLS volume cleaned"
	@echo "- Annotations volume cleaned"

format:
	docker compose run --rm --no-deps processor bash -lc "\
		black processor tests lab && \
		printf '\033[32mBlack formatting complete\033[0m\n' && \
		ruff check --fix && \
		printf '\033[32mRuff formatting complete\033[0m\n'"

check:
	docker compose run --rm --no-deps processor bash -lc "\
		ruff check && \
		printf '\033[32mRuff check passed\033[0m\n' && \
		PYRIGHT_PYTHON_PATH=\$(which python3) pyright && \
		printf '\033[32mPyright check passed\033[0m\n' && \
		bandit -r processor lab && \
		printf '\033[32mBandit check passed\033[0m\n'"

test:
	docker compose run --rm --no-deps processor pytest --cov --cov-report=term --cov-report=term-missing

e2e:
	@bash e2e-test.sh

lab:
	docker compose run --rm --no-deps \
		-e DISPLAY \
		-v /tmp/.X11-unix:/tmp/.X11-unix:ro \
		processor python -m lab

lab-convert:
	docker compose run --rm --no-deps \
		--workdir /app \
		processor python lab/converter.py
