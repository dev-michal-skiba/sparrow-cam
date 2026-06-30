.PHONY: help build start stream stop clean-archive processor-build processor-format processor-check processor-test processor-export-ncnn e2e lab-build lab-run lab-format lab-check lab-test archive-api-build archive-api-format archive-api-check archive-api-test web-test web-format web-check

help:
	@echo "SparrowCam Local Development"
	@echo ""
	@echo "Available commands:"
	@echo "  make build                 - Build the Docker image"
	@echo "  make start                 - Start the application (nginx on :8080)"
	@echo "    OPENCV_LOGS=1            - Start with OpenCV debug logging enabled"
	@echo "  make stream                - Stream a sample video (SAMPLE=sparrow|pigeon|overlapping)"
	@echo "    SAMPLE=sparrow           - Sample file to stream (required)"
	@echo "    LOOP=1                   - Stream in loop (default: false)"
	@echo "  make stop                  - Stop the application and clean stream and annotation files"
	@echo "  processor-build            - Build the processor Docker image"
	@echo "  make processor-format      - Format processor code with black and ruff"
	@echo "  make processor-check       - Run lint, type and security checks for processor"
	@echo "  make processor-test        - Run unit tests for processor package"
	@echo "    ARGS=\"..."              - Run with extra pytest flags (e.g. -vv for verbose output)"
	@echo "  make processor-export-ncnn - Export YOLO model to NCNN format (downloads if missing)"
	@echo "    MODEL=yolo26n.pt         - Model filename in models/ directory"
	@echo "  make e2e                   - Run end-to-end integration tests"
	@echo "  make lab-build             - Build the lab Docker image"
	@echo "  make lab-run               - Launch lab GUI (files auto-update)"
	@echo "  make lab-format            - Format lab code with black and ruff"
	@echo "  make lab-check             - Run lint, type and security checks for lab"
	@echo "  make lab-test              - Run unit tests for lab package"
	@echo "    ARGS=\"..."              - Run with extra pytest flags (e.g. -vv for verbose output)"
	@echo "  make archive-api-build     - Build the archive API Docker image"
	@echo "  make archive-api-format    - Format archive API code with black and ruff"
	@echo "  make archive-api-check     - Run lint, type and security checks for archive API"
	@echo "  make archive-api-test      - Run unit tests for archive API package"
	@echo "    ARGS=\"..."              - Run with extra pytest flags (e.g. -vv for verbose output)"

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
	@if [ -z "$(SAMPLE)" ]; then \
		echo "Error: SAMPLE is required. Valid values: sparrow, pigeon, overlapping"; \
		echo "Usage: make stream SAMPLE=sparrow"; \
		exit 1; \
	fi
	@if [ "$(SAMPLE)" != "sparrow" ] && [ "$(SAMPLE)" != "pigeon" ] && [ "$(SAMPLE)" != "overlapping" ]; then \
		echo "Error: invalid SAMPLE '$(SAMPLE)'. Valid values: sparrow, pigeon, overlapping"; \
		exit 1; \
	fi
	docker compose exec processor ffmpeg \
		$(if $(filter 1,$(LOOP)),-stream_loop -1) \
		-re \
		-i /app/samples/$(SAMPLE).mp4 \
		-c:v libx264 \
		-preset ultrafast \
		-g 8 \
		-keyint_min 8 \
		-sc_threshold 0 \
		-pix_fmt yuv420p \
		-an \
		-f hls \
		-hls_time 1 \
		-hls_list_size 60 \
		-hls_flags delete_segments+append_list \
		-hls_segment_filename "/var/www/html/hls/sparrow_cam-%d.ts" \
		/var/www/html/hls/sparrow_cam.m3u8

stop:
	docker compose down -v

clean-archive:
	docker compose exec processor sh -c "rm -rf /var/www/html/storage/sparrow_cam/archive/*"

processor-build:
	docker compose build processor

processor-format:
	docker compose run --rm --no-deps processor bash -lc "\
		black processor tests && \
		printf '\033[32mBlack formatting complete\033[0m\n' && \
		ruff check --fix && \
		printf '\033[32mRuff formatting complete\033[0m\n'"

processor-check:
	docker compose run --rm --no-deps processor bash -lc "\
		ruff check && \
		printf '\033[32mRuff check passed\033[0m\n' && \
		PYRIGHT_PYTHON_PATH=\$(which python3) pyright && \
		printf '\033[32mPyright check passed\033[0m\n' && \
		bandit -r processor && \
		printf '\033[32mBandit check passed\033[0m\n'"

processor-test:
	docker compose run --rm --no-deps processor pytest --cov --cov-report=term --cov-report=term-missing $(ARGS)

processor-export-ncnn:
	docker compose run --rm --no-deps processor python -m processor.scripts.export_ncnn $(MODEL)

e2e:
	@../bin/e2e-test


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
	docker compose -f docker-compose.lab.yml run --rm --no-deps lab pytest --cov --cov-report=term --cov-report=term-missing $(ARGS)


archive-api-build:
	docker compose build archive_api

archive-api-format:
	docker compose run --rm --no-deps archive_api bash -lc "\
		black archive_api tests && \
		printf '\033[32mBlack formatting complete\033[0m\n' && \
		ruff check --fix && \
		printf '\033[32mRuff formatting complete\033[0m\n'"

archive-api-check:
	docker compose run --rm --no-deps archive_api bash -lc "\
		ruff check && \
		printf '\033[32mRuff check passed\033[0m\n' && \
		PYRIGHT_PYTHON_PATH=\$(which python3) pyright && \
		printf '\033[32mPyright check passed\033[0m\n' && \
		bandit -r archive_api && \
		printf '\033[32mBandit check passed\033[0m\n'"

archive-api-test:
	docker compose run --rm --no-deps archive_api pytest --cov --cov-report=term --cov-report=term-missing $(ARGS)


web-test:
	@echo "Web package has no tests — skipping"

web-format:
	@echo "Web package has no formatting — skipping"

web-check:
	@echo "Web package has no lint/type checks — skipping"
