# SparrowCam

Local bird feeder observation system. Monitors camera feed, automatically detects birds, and streams HLS video. Runs entirely on your home network.

## Features

- Local-first (no cloud dependency)
- Automatic bird detection via YOLOv8
- Real-time HLS video streaming
- Web interface on your local network
- Live bird detection status display

## Project Structure

- **`local/`** - Local development environment
- **`deploy/`** - Production deployment to Raspberry Pi
- **`app/`** - nginx configurations and web interface

See individual README files for details.

## Quick Start

### Local Development

```bash
make -C local build
make -C local start
make -C local stop

# Access: http://localhost:8080
# Stream: rtmp://localhost:8081/live/sparrow_cam

# Code quality checks
make -C local check

# Run tests
make -C local test
```

See [local/README.md](local/README.md)

### Deploy to Raspberry Pi

```bash
# Setup (one-time)
make -C deploy build
make -C deploy ping

# Deploy
make -C deploy all

# Access: http://<pi-ip>/
# Stream: rtmp://<pi-ip>/live/sparrow_cam
```

See [deploy/README.md](deploy/README.md)

## Architecture

Three services:
- **Web Server** - Serves interface, HLS streams, and bird detection annotations
- **RTMP Server** - Receives RTMP video, generates HLS segments for streaming
- **Processor** - Detects birds in HLS segments, outputs real-time annotations

**Local dev**: Three Docker containers (ports 8080, 8081, plus shared volumes for HLS/annotations)

**Production**: Three systemd services on Raspberry Pi (nginx, nginx-rtmp, sparrow-processor)

## Requirements

**Development**: Docker, Docker Compose, ffmpeg

**Target Device**: Raspberry Pi with Ubuntu Server 25.04, SSH access
