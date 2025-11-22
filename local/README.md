# Local Development

Docker-based local development environment with three services:
- **rtmp**: nginx rtmp server on port 8081
- **processor**: HLS segment processor (video processing pipeline)
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

# Run formatting, lint, type and security checks
make -C local check

# Run unit tests
make -C local test

# Run end-to-end integration tests
make -C local e2e
```

## Services

**rtmp**: Runs nginx rtmp server
- RTMP: rtmp://localhost:8081/live/sparrow_cam

**processor**: Monitors HLS segments and applies frame-level processing
- Reads from shared HLS volume
- Processes each segment (currently: grayscale conversion)
- Outputs to processed_hls volume

**web**: Runs nginx web server
- Web: http://localhost:8080

## Usage

**Stream video**:
```bash
ffmpeg -re -stream_loop -1 -i sample.mp4 -c copy -f flv rtmp://localhost:8081/live/sparrow_cam
```

**Access HLS streams**:
- Original: http://localhost:8080/hls/sparrow_cam.m3u8
- Processed: http://localhost:8080/processed_hls/sparrow_cam.m3u8

## Code Quality and Testing

```bash
# Run formatting, linting, type checking, and security analysis
make -C local check

# Run unit tests with coverage report
make -C local test

# Run end-to-end integration tests
make -C local e2e
```

**Check** performs:
- `black` - Code formatting
- `ruff` - Linting
- `pyright` - Type checking
- `bandit` - Security analysis

**E2E Tests** verify the complete system:
- RTMP server accepts streams and generates HLS segments
- Processor service monitors HLS directory and creates annotations
- Web server serves HLS stream and annotations file
- Shared volumes enable communication between all three services

**E2E Test Host Requirements**:
- `docker` and `docker-compose` installed
- `ffmpeg` installed (for streaming test video)
- `curl` and `nc` (netcat) available on PATH
- Ports 8080 and 8081 available on localhost
- `sample.mp4` file in project root (used for streaming test)

## Debugging

**Debug OpenCV with logs**:
```bash
make -C local start OPENCV_LOGS=1
```

**Monitor service logs**:
```bash
# RTMP server logs
docker logs -f sparrow_cam_rtmp

# Processor logs (shows bird detection)
docker logs -f sparrow_cam_processor

# Web server logs
docker logs -f sparrow_cam_web

# All services
docker logs -f sparrow_cam_rtmp & docker logs -f sparrow_cam_processor & docker logs -f sparrow_cam_web
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
