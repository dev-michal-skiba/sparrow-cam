# Local Development

Docker-based local development environment with two services:
- **sparrow-cam**: nginx servers (web on :8080, RTMP on :8081)
- **processor**: HLS segment processor (video processing pipeline)

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
```

## Services

**sparrow-cam**: Runs nginx web server and nginx-rtmp using supervisord
- Web: http://localhost:8080
- RTMP: rtmp://localhost:8081/live/sparrow_cam

**processor**: Monitors HLS segments and applies frame-level processing
- Reads from shared HLS volume
- Processes each segment (currently: grayscale conversion)
- Outputs to processed_hls volume

## Usage

**Stream video**:
```bash
ffmpeg -re -stream_loop -1 -i poc/sample.mp4 -c copy -f flv rtmp://localhost:8081/live/sparrow_cam
```

**Access HLS streams**:
- Original: http://localhost:8080/hls/sparrow_cam.m3u8
- Processed: http://localhost:8080/processed_hls/sparrow_cam.m3u8

**Troubleshooting**:
```bash
# Check logs
docker logs sparrow_cam_local
docker logs sparrow_cam_processor

# View processor details
docker logs -f sparrow_cam_processor
```
