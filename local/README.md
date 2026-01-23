# Local Development

Docker-based local development environment with two services:
- **processor**: HLS segment processor (bird detection pipeline)
- **web**: nginx server on port 8080

## Quick Start

```bash
# Build
make -C local build

# Start all services
make -C local start

# Stop
make -C local stop

# Clean up everything
make -C local clean

# Format code with black and ruff
make -C local format

# Run code quality checks (linting, type, security - no formatting)
make -C local check

# Run unit tests
make -C local test

# Run end-to-end integration tests
make -C local e2e
```

## Services

**processor**: Monitors HLS segments and detects birds
- Reads from shared HLS volume (created by ffmpeg running separately)
- Processes each segment for bird detection
- Outputs annotations to shared annotations volume

**web**: Runs nginx web server
- Web: http://localhost:8080

## Setup

HLS segments must be generated externally by ffmpeg. Run ffmpeg separately in a separate terminal to generate HLS segments:

```bash
ffmpeg \
  -stream_loop -1 \
  -re \
  -i sample.mp4 \
  -c:v libx264 \
  -preset ultrafast \
  -b:v 500k \
  -maxrate 500k \
  -bufsize 1000k \
  -c:a aac \
  -b:a 128k \
  -f hls \
  -hls_time 2 \
  -hls_list_size 10 \
  local/hls/sparrow_cam.m3u8
```

**Access HLS streams**:
- http://localhost:8080/hls/sparrow_cam.m3u8

## Code Quality and Testing

```bash
# Format code with black and ruff
make -C local format

# Run code quality checks (linting, type checking, and security analysis)
make -C local check

# Run unit tests with coverage report
make -C local test

# Run end-to-end integration tests
make -C local e2e
```

**Format** performs:
- `black` - Code formatting
- `ruff check --fix` - Linting with auto-fixes

**Check** performs (verification only):
- `ruff check` - Linting verification
- `pyright` - Type checking
- `bandit` - Security analysis

**E2E Tests** verify the complete system:
- Processor service monitors HLS directory and creates annotations
- Web server serves HLS stream and annotations file
- Shared volumes enable communication between services

**E2E Test Host Requirements**:
- `docker` and `docker-compose` installed
- `curl` available on PATH
- Ports 8080 available on localhost

## Debugging

**Debug OpenCV with logs**:
```bash
make -C local start OPENCV_LOGS=1
```

**Monitor service logs**:
```bash
# Processor logs (shows bird detection)
docker logs -f sparrow_cam_processor

# Web server logs
docker logs -f sparrow_cam_web

# All services
docker logs -f sparrow_cam_processor & docker logs -f sparrow_cam_web
```

**Check service health**:
```bash
docker ps
docker compose ps
```

**Inspect volumes and data**:
```bash
# List volumes
docker volume ls | grep sparrow_cam

# Inspect specific volume
docker volume inspect local_hls_data
docker volume inspect local_annotations_data
```

## Data Management

**Clean HLS segments and annotations** (keeps containers running):
```bash
make -C local clean
```

**Full cleanup** (stops and removes containers, volumes, and images):
```bash
docker compose down -v --rmi all
```

## Annotations

The processor generates bird detection annotations in `/var/www/html/annotations/bird.json` which the web server hosts. Access via:
- HTTP: `http://localhost:8080/annotations/bird.json`
- Docker volume: `local_annotations_data`

## Troubleshooting

```bash
# Check container status
docker compose ps

# View container logs (last 50 lines)
docker logs -n 50 sparrow_cam_processor

# Rebuild images (useful if dependencies changed)
make -C local build

# Restart all services
make -C local stop && make -C local start

# Check Docker disk usage
docker system df
```
