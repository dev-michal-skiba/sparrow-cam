.PHONY: help build start stop clean unit

help:
	@echo "SparrowCam Local Development"
	@echo ""
	@echo "Available commands:"
	@echo "  make build                - Build the Docker image"
	@echo "  make start                - Start the application (web on :8080, RTMP on :8081)"
	@echo "  make start OPENCV_LOGS=1  - Start with OpenCV debug logging enabled"
	@echo "  make stop                 - Stop the application"
	@echo "  make clean                - Stop and remove containers, volumes, and generated files"
	@echo "  make unit                 - Run unit tests for processor package"

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
	@echo "  ffmpeg -re -stream_loop -1 -i poc/sample.mp4 -c copy -f flv rtmp://localhost:8081/live/sparrow_cam"

stop:
	docker compose down

clean:
	docker compose down -v
	docker run --rm -v $(PWD)/recordings:/recordings -v $(PWD)/hls:/hls alpine sh -c "rm -rf /recordings/* /hls/*"

unit:
	docker compose run --rm --no-deps processor pytest tests/ -v
