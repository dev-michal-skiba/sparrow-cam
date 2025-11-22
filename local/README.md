# Local Development

Docker-based local development environment with two services:
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

**Troubleshooting**:
```bash
# Check logs
docker logs sparrow_cam_rtmp
docker logs sparrow_cam_processor
docker logs sparrow_cam_web
```
