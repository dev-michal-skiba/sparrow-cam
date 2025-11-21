.PHONY: help build start stop clean check test

help:
	@echo "SparrowCam Local Development"
	@echo ""
	@echo "Available commands:"
	@echo "  make build                 - Build the Docker image"
	@echo "  make check                 - Run formatting, lint, type and security checks"
	@echo "  make start                 - Start the application (web on :8080, RTMP on :8081)"
	@echo "  make start OPENCV_LOGS=1   - Start with OpenCV debug logging enabled"
	@echo "  make stop                  - Stop the application"
	@echo "  make clean                 - Stop and remove containers, volumes, and generated files"
	@echo "  make test                  - Run unit tests for processor package"

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
	docker compose run --rm --entrypoint sh sparrow-cam -c "\
		rm -rf /var/www/html/hls/* && \
		rm -rf /var/www/html/annotations/*"
	@echo "Cleanup completed successfully"
	@echo "- HLS volume cleaned"
	@echo "- Annotations volume cleaned"

check:
	docker compose run --rm --no-deps processor bash -lc "\
		black processor tests && \
		printf '\033[32mBlack formatting complete\033[0m\n' && \
		ruff check && \
		printf '\033[32mRuff check passed\033[0m\n' && \
		PYRIGHT_PYTHON_PATH=\$(which python3) pyright && \
		printf '\033[32mPyright check passed\033[0m\n' && \
		bandit -r processor && \
		printf '\033[32mBandit check passed\033[0m\n'"

test:
	docker compose run --rm --no-deps processor pytest --cov=processor --cov-report=term --cov-report=term-missing
