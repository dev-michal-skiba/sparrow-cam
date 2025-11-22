# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SparrowCam is a local bird feeder observation system that monitors a camera feed, automatically detects birds, and records video clips. The system runs entirely on a local network (typically on a Raspberry Pi) with no cloud dependency.

## Repository Structure

### `app/`
Main application directory containing:
- **nginx-web.conf**: Web server (nginx) configuration for port 80
- **nginx-rtmp.conf**: RTMP server (nginx-rtmp) configuration for port 1935
- **nginx-rtmp.service**: Systemd service file for RTMP server
- **index.html**: Simple web interface that displays the video stream
- **processor/**: Python video processing service
  - `processor/app.py`: HLSSegmentProcessor - monitors and processes HLS segments frame-by-frame
  - `setup.py`: Package configuration with opencv-python dependency (excludes tests from package)
  - `tests/test_app.py`: Pytest-based unit tests

### `local/`
Local development environment using Docker:
- **Makefile**: Defines local development commands (build, start, stop, clean)
- **Dockerfile**: Creates local development container with nginx, nginx-rtmp, supervisord
- **Dockerfile.processor**: Creates processor service container (Python 3.13, OpenCV, FFmpeg)
- **docker-compose.yml**: Orchestrates both services and shared HLS volumes
- **supervisord.conf**: Configuration for running both nginx processes

See `local/README.md` for detailed usage instructions.

### `tests/`
Testing suite for the application:
- **Makefile**: Defines test commands
- **e2e-test.sh**: End-to-end tests that verify the full system functionality

See `tests/README.md` for detailed testing instructions.

### `deploy/`
Ansible-based deployment system that deploys to local server (typically Raspberry Pi):
- **Makefile**: Defines deployment commands
- **Dockerfile**: Creates Ansible container with Alpine Linux, Ansible, and SSH tools
- **docker-compose.yml**: Orchestrates deployment container
- **ansible/**: Contains playbooks and configuration
  - `web.yml`: Deploys web server (nginx on port 80)
  - `rtmp.yml`: Deploys RTMP server (nginx-rtmp on port 1935)
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
- `hls_data`: Original HLS segments and playlist from RTMP server
- `processed_hls_data`: Processed HLS segments and playlist from processor

### Deployed System

The target system (Raspberry Pi) also consists of **two separate nginx services**:

1. **Web Server (nginx)** - Port 80
   - Serves web interface (index.html)
   - Serves HLS streams to browsers
   - Config: `/etc/nginx/nginx.conf` (from `app/nginx-web.conf`)

2. **RTMP Server (nginx-rtmp)** - Port 1935
   - Receives RTMP video streams
   - Generates HLS output for web playback
   - Records streams to disk
   - Config: `/etc/nginx-rtmp/nginx.conf` (from `app/nginx-rtmp.conf`)
   - Runs as separate systemd service: `nginx-rtmp.service`

Note: Processor service not yet deployed - currently local-only for development.

## Common Development Commands

### Local Development

The project is organized into three packages, each with its own Makefile:

**View available packages:**
```bash
make help
# Shows: local, tests, and deploy packages
```

**Local development commands** (run from project root):
```bash
# Build the Docker image
make -C local build

# Start the application
make -C local start
# Web server runs on http://localhost:8080
# RTMP server accepts streams on rtmp://localhost:8081/live/sparrow_cam

# Stop the application
make -C local stop

# Clean up (stop containers and remove generated files)
make -C local clean

# Run processor unit tests
make -C local unit

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

**Processor pipeline:**
- Watch HLS directory: `/var/www/html/hls`
- Process each segment with frame-level operations (currently: grayscale conversion)
- Output to: `/var/www/html/processed_hls`
- Access processed stream at: `http://localhost:8080/processed_hls/sparrow_cam.m3u8`

### Testing

**Run end-to-end tests** (run from project root):
```bash
make -C tests e2e
```

**Run processor unit tests** (run from project root):
```bash
make -C local unit
```

**End-to-end tests verify:**
- Docker availability and image build
- Container startup and health
- Web server responds on port 8080
- RTMP server accepts streams on port 8081
- HLS stream generation
- Recording file creation
- Both nginx processes running under supervisord

Tests automatically:
- Build the local development image
- Start containers
- Stream test video
- Verify all functionality
- Clean up containers and files

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

# Deploy both servers
make -C deploy all

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

# Update both
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
```

**View logs:**
```bash
# Web server logs
ssh <user>@<ip> "sudo tail -f /var/log/nginx/error.log"

# RTMP server logs
ssh <user>@<ip> "sudo journalctl -u nginx-rtmp -f"
```

**Restart services:**
```bash
# Web server
ssh <user>@<ip> "sudo systemctl restart nginx"

# RTMP server
ssh <user>@<ip> "sudo systemctl restart nginx-rtmp"
```

## Technical Requirements

- **Target device**: Raspberry Pi 4/5 or similar ARM/x64 device
- **Target OS**: Ubuntu Server 25.04 64-bit recommended
- **Network**: Development machine and target device must be on same local network
- **SSH**: Target device must have SSH server on port 22 with a user account with sudo privileges
- **Development machine**: Docker and Docker Compose required
