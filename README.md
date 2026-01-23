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

# Format code (black and ruff)
make -C local format

# Code quality checks (linting, type, security)
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
```

See [deploy/README.md](deploy/README.md)

## Architecture

Three components (two services plus external stream):
- **Web Server** - Serves interface, HLS streams, and bird detection annotations
- **Processor** - Detects birds in HLS segments, outputs real-time annotations
- **Stream** - Captures USB camera feed and generates HLS segments using ffmpeg

**Local dev**: Two Docker containers (port 8080, plus shared volumes for HLS/annotations)

**Production**: Two systemd services on Raspberry Pi (nginx, sparrow-processor) plus ffmpeg stream running in tmux

## Requirements

**Development**: Docker, Docker Compose, ffmpeg

**Target Device**: Raspberry Pi with Ubuntu Server 25.04, SSH access, USB webcam
