# Local Development

Docker-based local development environment. Runs both nginx services in a single container using supervisord.

## Quick Start

```bash
# Build
make -C local build

# Start (web on :8080, RTMP on :8081)
make -C local start

# Stop
make -C local stop

# Clean up everything
make -C local clean
```

## Usage

**Access**:
- Web: http://localhost:8080
- RTMP: rtmp://localhost:8081/live/sparrow_cam

**Stream video**:
```bash
ffmpeg -re -i poc/sample.mp4 -c copy -f flv rtmp://localhost:8081/live/sparrow_cam
```

**Troubleshooting**:
```bash
# Check logs
docker logs sparrow_cam_local

# Remove stuck container
docker rm -f sparrow_cam_local
```
