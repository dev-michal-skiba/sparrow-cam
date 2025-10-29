# SparrowCam

Local bird feeder observation system. Monitors camera feed, detects birds, and records video clips. Runs entirely on your home network.

## Features

- Local-first (no cloud dependency)
- Automatic bird detection and recording
- Web interface on your local network
- HLS video streaming
- Local video storage

## Project Structure

- **`local/`** - Local development environment
- **`tests/`** - End-to-end tests
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
```

See [local/README.md](local/README.md)

### Testing

```bash
# End-to-end tests
make -C tests e2e

# Processor unit tests
make -C local unit
```

See [tests/README.md](tests/README.md)

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

Two nginx services:
- **Web Server** (port 80) - Serves interface and HLS streams
- **RTMP Server** (port 1935) - Receives video, generates HLS, records

**Local dev**: Single container with supervisord (ports 8080/8081)
**Production**: Two systemd services on Raspberry Pi (ports 80/1935)

## Requirements

**Development**: Docker, Docker Compose, ffmpeg
**Target Device**: Raspberry Pi with Ubuntu Server 25.04, SSH access
