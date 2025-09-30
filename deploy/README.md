# Deployment Guide

Automated deployment to Raspberry Pi or similar devices using Dockerized Ansible.

## Prerequisites

### Target Server Requirements
- **Device**: Raspberry Pi 4/5 or similar ARM/x64 device
- **OS**: Ubuntu Server 25.04 64-bit (or compatible Linux distribution)
- **Network**: Must be on the same local network as your development machine
- **SSH**: SSH server installed and running on port 22
- **User**: A user account with sudo privileges

### Development Machine Requirements
- Docker and Docker Compose installed
- SSH key pair for authentication
- Network access to target server

## Initial Setup

### 1. Configure SSH Access

Generate an SSH key pair if you don't have one:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/sparrowcam_deploy
```

Copy your public key to the target server:
```bash
ssh-copy-id -i ~/.ssh/sparrowcam_deploy.pub <username>@<target-ip>
```

Copy your private key to the deploy directory:
```bash
cp ~/.ssh/sparrowcam_deploy ansible/ssh_key
chmod 600 ansible/ssh_key
```

### 2. Configure Ansible Variables

Copy the example variables file:
```bash
cp ansible/group_vars/all.yml.example ansible/group_vars/all.yml
```

Edit `ansible/group_vars/all.yml` with your target server details:
```yaml
ansible_target_host: "192.168.1.100"  # Your Raspberry Pi IP address
ansible_target_user: "pi"              # Your SSH username
```

### 3. Build the Deployment Container

Build the Docker image containing Ansible and required tools:
```bash
make -C deploy build
```

This creates a `sparrow_cam_deploy` Docker image with:
- Alpine Linux 3.22.1
- Ansible
- OpenSSH client
- SSH utilities

## Available Commands

Run these commands from the project root

### Help
```bash
make -C deploy help
# or simply
make -C deploy
```
Shows all available deployment commands.

### Build Container
```bash
make -C deploy build
```
Builds the deployment Docker container with Ansible installed.

### Test Connectivity
```bash
make -C deploy ping
```
Tests SSH connectivity to your target server using Ansible's ping module. This verifies:
- SSH key authentication works
- Target server is reachable
- Ansible can connect successfully

### Deploy Web Server
```bash
make -C deploy web
```
Deploys the web server (nginx) to your Raspberry Pi. This playbook:
- Installs nginx
- Creates HLS and recordings directories
- Copies nginx web configuration
- Copies the web interface (index.html)
- Configures proper permissions
- Opens port 80 in firewall
- Validates and restarts nginx

### Deploy RTMP Server
```bash
make -C deploy rtmp
```
Deploys the RTMP streaming server (nginx-rtmp) to your Raspberry Pi. This playbook:
- Installs nginx with RTMP module and ffmpeg
- Creates a separate nginx-rtmp service
- Copies RTMP configuration
- Creates HLS and recordings directories
- Opens port 1935 in firewall
- Validates and starts nginx-rtmp service

### Deploy Both Servers
```bash
make -C deploy all
```
Deploys both web server and RTMP server in sequence.

**Note**: All playbooks are idempotent - you can run them multiple times safely. They work for:
- **Initial setup**: First time deployment on a fresh Raspberry Pi
- **Updates**: Updating configurations or web interface files

## Testing Your Setup

After completing the initial setup, verify connectivity:

```bash
make -C deploy ping
```

Expected output:
```
server | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

If you see errors:
- Verify target server IP address is correct in `ansible/group_vars/all.yml`
- Check that target server is accessible: `ping <target-ip>`
- Test manual SSH connection: `ssh -i ansible/ssh_key <user>@<target-ip>`
- Verify port 22 is open on target server: `nc -zv <target-ip> 22`

## Complete Deployment Workflow

### First Time Deployment
```bash
# 1. Build the deployment container
make -C deploy build

# 2. Test connectivity
make -C deploy ping

# 3. Deploy both servers
make -C deploy all
```

### Updating Configurations

**Update web server** (`app/nginx-web.conf` or `app/index.html`):
```bash
make -C deploy web
```

**Update RTMP server** (`app/nginx-rtmp.conf`):
```bash
make -C deploy rtmp
```

**Update both**:
```bash
make -C deploy all
```

The playbooks will:
- Detect which files have changed
- Copy only the updated files
- Restart only the affected services

## Architecture

The deployment consists of **two separate nginx services**:

1. **Web Server (nginx)** - Port 80
   - Serves the web interface (index.html)
   - Serves HLS streams to browsers
   - Provides recordings directory browser
   - Config: `/etc/nginx/nginx.conf`

2. **RTMP Server (nginx-rtmp)** - Port 1935
   - Receives RTMP video streams
   - Generates HLS output
   - Records streams to disk
   - Config: `/etc/nginx-rtmp/nginx.conf`
   - Runs as separate systemd service: `nginx-rtmp.service`

## File Structure

```
deploy/
├── Makefile                          # Deployment commands
├── Dockerfile                        # Ansible container definition
├── docker-compose.yml                # Container orchestration
├── README.md                         # This file
└── ansible/
    ├── inventory.yml                 # Ansible inventory (uses variables)
    ├── web.yml                # Web server deployment playbook
    ├── rtmp.yml               # RTMP server deployment playbook
    ├── ssh_key                       # SSH private key (git-ignored)
    └── group_vars/
        ├── all.yml                   # Your actual variables (git-ignored)
        └── all.yml.example           # Template for variables (tracked in git)

app/
├── nginx-web.conf                    # Web server nginx config
├── nginx-rtmp.conf                   # RTMP server nginx config
├── nginx-rtmp.service                # RTMP systemd service file
└── index.html                        # Web interface
```

## Using the Deployed System

### Access Points

**Web Interface:**
```
http://<raspberry-pi-ip>/
```

**Stream Endpoint (for ffmpeg):**
```
rtmp://<raspberry-pi-ip>/live/sparrow_cam
```

**HLS Playlist (direct access):**
```
http://<raspberry-pi-ip>/hls/sparrow_cam.m3u8
```

**Recordings Browser:**
```
http://<raspberry-pi-ip>/recordings/
```

### Streaming with FFmpeg

From your laptop or any device:
```bash
ffmpeg -re -i input.mp4 -c copy -f flv rtmp://<raspberry-pi-ip>/live/sparrow_cam
```

### Checking Service Status

**Check web server:**
```bash
ssh <user>@<raspberry-pi-ip> "sudo systemctl status nginx"
```

**Check RTMP server:**
```bash
ssh <user>@<raspberry-pi-ip> "sudo systemctl status nginx-rtmp"
```

**Check both services:**
```bash
ssh <user>@<raspberry-pi-ip> "sudo systemctl status nginx nginx-rtmp"
```

### Troubleshooting

**View web server logs:**
```bash
ssh <user>@<raspberry-pi-ip> "sudo tail -f /var/log/nginx/error.log"
```

**View RTMP server logs:**
```bash
ssh <user>@<raspberry-pi-ip> "sudo journalctl -u nginx-rtmp -f"
```

**Restart services:**
```bash
# Restart web server
ssh <user>@<raspberry-pi-ip> "sudo systemctl restart nginx"

# Restart RTMP server
ssh <user>@<raspberry-pi-ip> "sudo systemctl restart nginx-rtmp"
```
