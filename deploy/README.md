# Deployment

Ansible-based deployment to Raspberry Pi or similar devices.

## Prerequisites

- Target device: Raspberry Pi with Ubuntu Server 25.04
- SSH access configured
- Same local network as development machine

## Initial Setup

**1. Generate SSH key**:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/sparrowcam_deploy
ssh-copy-id -i ~/.ssh/sparrowcam_deploy.pub <username>@<target-ip>
```

**2. Configure deployment**:
```bash
cp ~/.ssh/sparrowcam_deploy deploy/ansible/ssh_key
chmod 600 deploy/ansible/ssh_key

cp deploy/ansible/group_vars/all.yml.example deploy/ansible/group_vars/all.yml
# Edit all.yml with your target IP and username
```

**3. Build and test**:
```bash
make -C deploy build
make -C deploy ping
```

## Deploy

```bash
# Deploy web, RTMP, and processor services
make -C deploy all

# Or deploy separately
make -C deploy processor # Processor service
make -C deploy web       # Web server (port 80)
```

## Usage

**Access** (replace with your Pi's IP):
- Web: http://192.168.1.100/

**Stream video**:
```bash
ffmpeg -re -stream_loop -1 -i sample.mp4 -c copy -f flv rtmp://192.168.1.100/live/sparrow_cam
```

## Service Architecture

The deployment creates three systemd services on the target device:

1. **nginx** (port 80) - Web server
   - Serves web interface and HLS streams
   - Hosts annotation file from processor (`/var/www/html/annotations/bird.json`)
   - Configuration: `/etc/nginx/nginx.conf`

2. **sparrow-processor** - HLS segment processor
   - Monitors `/var/www/html/hls` for new segments
   - Processes each frame and detects birds
   - Outputs annotations to `/var/www/html/annotations/bird.json`
   - Runs as `sparrow_cam_processor` user

## Troubleshooting

```bash
# Check connectivity
make -C deploy ping

# Clean streaming data and annotations (keeps directories)
make -C deploy clean

# View service status
ssh <user>@<ip> "sudo systemctl status nginx sparrow-processor"

# View logs
ssh <user>@<ip> "sudo journalctl -u sparrow-processor -f"
ssh <user>@<ip> "sudo journalctl -u nginx -f"

# Restart individual services
ssh <user>@<ip> "sudo systemctl restart nginx"
ssh <user>@<ip> "sudo systemctl restart sparrow-processor"

# Check service files
ssh <user>@<ip> "ls -la /etc/systemd/system/ | grep -E 'nginx|sparrow'"
```

## Deployment Requirements

- **Target OS**: Ubuntu Server 25.04 (64-bit recommended)
- **SSH**: Target must have SSH enabled with key-based authentication
- **Sudo**: SSH user must have passwordless sudo privileges
- **Network**: Target device must be accessible from development machine
- **Firewall**: Playbooks configure UFW to allow SSH (22), HTTP (80), and RTMP (1935)
- **Disk Space**: Ensure sufficient space for HLS segments and recordings

## Updating Configurations

All Ansible playbooks are idempotent - run them anytime to update:

```bash
# After modifying app/nginx-web.conf or app/index.html
make -C deploy web


# After modifying processor app
make -C deploy processor

# Update all configurations
make -C deploy all
```

## Directory Locations

On the target device:

```
/var/www/html/hls/                            # HLS segments and playlist
/var/www/html/annotations/bird.json           # Bird detection annotations
/var/www/html/index.html                      # Web interface
/etc/nginx/nginx.conf                         # Web server config
/etc/systemd/system/sparrow-processor.service # Processor service file
/opt/sparrow_cam_processor/                   # Processor home directory
```
