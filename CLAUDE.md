# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SparrowCam is a local bird feeder observation system that monitors a camera feed, automatically detects birds via YOLOv8, and streams HLS video. The system runs entirely on a local network (typically on a Raspberry Pi) with no cloud dependency.

## Repository Structure

### `app/`
Main application directory containing configurations and processor service:

**Nginx Configuration**:
- **nginx-web.conf**: Web server configuration (template with ${WEB_PORT} substitution)
  - Serves web interface on configurable port
  - Serves HLS streams from `/var/www/html/hls/` with CORS headers
  - Serves bird detection annotations from `/var/www/html/annotations/bird.json`
- **nginx-rtmp.conf**: RTMP server configuration (template with ${RTMP_PORT} substitution)
  - Receives RTMP streams on configurable port
  - Generates HLS segments to `/var/www/html/hls/`
  - HLS fragment: 1s
  - HLS playlist: 60s buffer
- **nginx-rtmp.service**: Systemd service file for RTMP server
  - Type: forking with PIDFile tracking
  - Validates config before startup

**Web Interface**:
- **index.html**: Interactive web interface with HLS.js
  - Displays live video stream using HLS protocol
  - Shows current HLS segment filename
  - Displays bird detection status (fetched every 500ms from `/annotations/bird.json`)
  - Responsive design with video player controls

**Processor Service** (Python package at `processor/`):
- **pyproject.toml**: Package configuration
  - Name: `processor`, version: `0.1.0`
  - Requires Python >=3.11
  - Dependencies: `opencv-python-headless`, `ultralytics`
  - Test coverage requirement: >=90%
  - Linting: ruff (line length 120), black, pyright
- **processor/__main__.py**: Entry point
  - Initializes and runs HLSSegmentProcessor
  - Sets up logging to stdout
- **processor/hls_segment_processor.py**: Main orchestrator
  - Coordinates bird detection and annotation
  - Processes segments: reads first frame, detects birds, logs results
  - Measures and logs processing time per segment
- **processor/bird_detector.py**: Bird detection engine
  - Uses YOLOv8 nano model (`yolov8n.pt`)
  - Detects birds (COCO class ID 14) at 480px resolution
  - Returns boolean: bird detected or not
- **processor/bird_annotator.py**: Annotation persistence
  - Reads/writes annotations to `/var/www/html/annotations/bird.json`
  - Prunes outdated annotations for segments no longer in HLS playlist
  - Handles file corruption/missing file gracefully
- **processor/hls_watchtower.py**: HLS playlist monitor
  - Monitors `/var/www/html/hls/sparrow_cam.m3u8` for new segments
  - Yields each new segment path exactly once
  - Exponential backoff retry (1-10s) if playlist not available
  - Polls every 1 second for new segments
- **tests/**: Test suite
  - `conftest.py`: Pytest configuration
  - `test_app.py`: HLSSegmentProcessor tests
  - `test_bird_detector.py`: Bird detection tests with sample images
  - `test_bird_annotator.py`: Annotation persistence tests
  - `test_hls_watchtower.py`: Playlist monitoring tests
  - `data/`: Test images (bird.png, no_bird.png)

### `local/`
Local development environment using Docker with three services:
- **Makefile**: Defines local development commands (build, start, stop, clean, check, test, e2e)
- **e2e-test.sh**: End-to-end integration test script
  - Tests complete pipeline: RTMP → HLS → Processor → Annotations → Web
  - 28 individual test assertions across 7 test phases
  - Validates bird detection processing and error-free operation
  - Automatic cleanup on success or failure
  - Requirements: docker, ffmpeg, curl, nc, sample.mp4
- **Dockerfile.rtmp**: Creates nginx RTMP server container (Ubuntu 25.04, nginx with RTMP module)
- **Dockerfile.web**: Creates nginx web server container (Ubuntu 25.04, serves interface and annotations)
- **Dockerfile.processor**: Creates processor service container (Python 3.13, OpenCV, FFmpeg, ultralytics)
- **docker-compose.yml**: Orchestrates three services with shared HLS and annotations volumes
- **requirements.dev.txt**: Development dependencies (pytest, ruff, black, pyright, bandit)

See `local/README.md` for detailed usage instructions.

### `deploy/`
Ansible-based deployment system that deploys to local server (typically Raspberry Pi):
- **Makefile**: Defines deployment commands (build, ping, web, rtmp, processor, all, clean)
- **Dockerfile**: Creates Ansible container with Alpine Linux, Ansible, and SSH tools
- **docker-compose.yml**: Orchestrates deployment container with volume mounts to `app/`
- **ansible/**: Contains playbooks and configuration
  - `web.yml`: Deploys web server (nginx on port 80) serving interface and annotations
  - `rtmp.yml`: Deploys RTMP server (nginx-rtmp on port 1935) with systemd service
  - `processor.yml`: Deploys processor service (pyenv, Python virtualenv, systemd service)
  - `clean.yml`: Cleans HLS segments and annotation files from target device
  - `inventory.yml`: Defines target server using variables
  - `group_vars/all.yml`: Target device IP and SSH username (git-ignored)
  - `group_vars/all.yml.example`: Template for variables
  - `ssh_key`: SSH private key for authentication (git-ignored)

See `deploy/README.md` for detailed deployment instructions.

## Architecture

### Local Development Stack

Three services communicate via shared volumes:

1. **RTMP Server (nginx-rtmp)** - Port 8081
   - Receives RTMP streams from clients
   - Generates HLS segments to shared volume → `/var/www/html/hls`

2. **Processor Service (Python)** - Background
   - Monitors shared volume `/var/www/html/hls` for new segments
   - Processes each segment and detects birds
   - Each segment is annotated in `/var/www/html/annotations/bird.json`

1. **Web Server (nginx)** - Port 8080
   - Serves web interface (index.html)
   - Serves HLS stream
   - Serves annonations file `/var/www/html/annotations/bird.json`
   - Root: `/var/www/html`

**Shared Volumes**:
- `hls_data`: HLS segments and playlist generated by RTMP server (consumed by processor and web server)
- `annotations_data`: Bird detection annotations from processor (served by web server)

### Deployed System

The target system (Raspberry Pi) consists of **three systemd services**:

1. **Web Server (nginx)** - Port 80
   - Serves web interface (index.html)
   - Serves HLS streams to browsers
   - Hosts bird detection annotations (`/var/www/html/annotations/bird.json`)
   - Config: `/etc/nginx/nginx.conf` (from `app/nginx-web.conf`)
   - Systemd service: `nginx`

2. **RTMP Server (nginx-rtmp)** - Port 1935
   - Receives RTMP video streams
   - Generates HLS output for web playback
   - Config: `/etc/nginx-rtmp/nginx.conf` (from `app/nginx-rtmp.conf`)
   - Systemd service: `nginx-rtmp.service`

3. **Processor Service** - Background
   - Installed via pyenv with Python virtualenv at `/opt/sparrow_cam_processor`
   - Monitors `/var/www/html/hls` for new segments
   - Processes frames and detects birds
   - Outputs annotations to `/var/www/html/annotations/bird.json`
   - Runs as `sparrow_cam_processor` user
   - Systemd service: `sparrow-processor`

## Common Development Commands

### Local Development

The project is organized into three packages, each with its own Makefile:

**View available packages:**
```bash
make help
# Shows: local and deploy packages
```

**Local development commands** (run from project root):
```bash
# Build the Docker images
make -C local build

# Start all services
make -C local start
# Web server runs on http://localhost:8080
# RTMP server accepts streams on rtmp://localhost:8081/live/sparrow_cam

# Stop all services
make -C local stop

# Clean HLS and annotations data (containers keep running)
make -C local clean

# Format code (black and ruff --fix)
make -C local format

# Run code quality checks (linting, type checking, security - no formatting)
make -C local check

# Run processor tests with coverage report
make -C local test

# Run end-to-end integration tests
make -C local e2e

# Start with OpenCV debug logging enabled
make -C local start OPENCV_LOGS=1

# View all local commands
make -C local help
```

**Local development architecture:**
- Docker containers
   - `rtmp` container: nginx-rtmp (port 8081)
   - `processor` container: HLS segment processing pipeline
   - `web` container: nginx-web (port 8080)
- Shared volumes
   - HLS data exchange between all containers
   - Annotations data echange between `processor` and `web` container
- Build context is project root, allowing access to `app/` files

**Streaming to local development:**
```bash
ffmpeg -re -stream_loop -1 -i sample.mp4 -c copy -f flv rtmp://localhost:8081/live/sparrow_cam
```

**Code Quality Tools**:
The `make -C local format` command runs:
- `black` - Code formatting
- `ruff check --fix` - Linting with auto-fixes

The `make -C local check` command runs (verification only, no formatting):
- `ruff check` - Linting verification
- `pyright` - Type checking
- `bandit` - Security analysis

**Debugging**:
```bash
# View logs for specific service
docker logs -f sparrow_cam_processor
docker logs -f sparrow_cam_rtmp
docker logs -f sparrow_cam_web

# Check Docker volumes
docker volume ls | grep sparrow_cam
```

**Processor pipeline**:
- Monitors HLS directory: `/var/www/html/hls` for new segments
- Processes each segment first frame (bird detection via ultralytics)
- Outputs annotations to: `/var/www/html/annotations/bird.json`
- Web server hosts annotations at: `http://localhost:8080/annotations/bird.json`

### Deployment Operations

All deployment commands run from project root:

```bash
# Build deployment container (required first time)
make -C deploy build

# Test connectivity to target device
make -C deploy ping

# Deploy web server (nginx on port 80)
make -C deploy web

# Deploy RTMP server (nginx-rtmp on port 1935)
make -C deploy rtmp

# Deploy processor service
make -C deploy processor

# Deploy all services (rtmp, processor, web)
make -C deploy all

# Clean HLS segments and annotations on target device
make -C deploy clean

# View all available commands
make -C deploy help
```

### Initial Deployment Setup

1. Generate SSH key pair:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/sparrowcam_deploy
   ```

2. Copy public key to target device:
   ```bash
   ssh-copy-id -i ~/.ssh/sparrowcam_deploy.pub <username>@<target-ip>
   ```

3. Copy private key to deploy directory:
   ```bash
   cp ~/.ssh/sparrowcam_deploy deploy/ansible/ssh_key
   chmod 600 deploy/ansible/ssh_key
   ```

4. Configure Ansible variables:
   ```bash
   cp deploy/ansible/group_vars/all.yml.example deploy/ansible/group_vars/all.yml
   # Edit all.yml with target device IP and SSH username
   ```

5. Build and test:
   ```bash
   make -C deploy build
   make -C deploy ping
   ```

6. Deploy:
   ```bash
   make -C deploy all
   ```

### Updating Configurations

Ansible playbooks are idempotent - run them anytime to update configurations:

```bash
# After editing app/nginx-web.conf or app/index.html
make -C deploy web

# After editing app/nginx-rtmp.conf
make -C deploy rtmp

# After editing app/processor code
make -C deploy processor

# Update all services
make -C deploy all
```

### Using the Deployed System

**Stream video to the system:**
```bash
ffmpeg -re -i input.mp4 -c copy -f flv rtmp://<raspberry-pi-ip>/live/sparrow_cam
```

**Access points:**
- Web interface: `http://<raspberry-pi-ip>/`
- HLS playlist: `http://<raspberry-pi-ip>/hls/sparrow_cam.m3u8`

**Check service status:**
```bash
# Web server
ssh <user>@<ip> "sudo systemctl status nginx"

# RTMP server
ssh <user>@<ip> "sudo systemctl status nginx-rtmp"

# Processor service
ssh <user>@<ip> "sudo systemctl status sparrow-processor"

# All services
ssh <user>@<ip> "sudo systemctl status nginx nginx-rtmp sparrow-processor"
```

**View logs:**
```bash
# Web server logs
ssh <user>@<ip> "sudo journalctl -u nginx -f"

# RTMP server logs
ssh <user>@<ip> "sudo journalctl -u nginx-rtmp -f"

# Processor service logs
ssh <user>@<ip> "sudo journalctl -u sparrow-processor -f"
```

**Restart services:**
```bash
# Web server
ssh <user>@<ip> "sudo systemctl restart nginx"

# RTMP server
ssh <user>@<ip> "sudo systemctl restart nginx-rtmp"

# Processor service
ssh <user>@<ip> "sudo systemctl restart sparrow-processor"
```

## Technical Requirements

- **Target device**: Raspberry Pi 4/5 or similar ARM/x64 device
- **Target OS**: Ubuntu Server 25.04 64-bit recommended
- **Network**: Development machine and target device must be on same local network
- **SSH**: Target device must have SSH server on port 22 with a user account with sudo privileges
- **Development machine**: Docker and Docker Compose required
