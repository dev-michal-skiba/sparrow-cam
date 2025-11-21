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
cp ~/.ssh/sparrowcam_deploy ansible/ssh_key
chmod 600 ansible/ssh_key

cp ansible/group_vars/all.yml.example ansible/group_vars/all.yml
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
make -C deploy web       # Web server (port 80)
make -C deploy rtmp      # RTMP server (port 1935)
make -C deploy processor # Processor service
```

## Usage

**Access** (replace with your Pi's IP):
- Web: http://192.168.1.100/
- RTMP: rtmp://192.168.1.100/live/sparrow_cam

**Stream video**:
```bash
ffmpeg -re -stream_loop -1 -i sample.mp4 -c copy -f flv rtmp://192.168.1.100/live/sparrow_cam
```

## Troubleshooting

```bash
# Check connectivity
make -C deploy ping

# Clean HLS files and recordings (keeps directories)
make -C deploy clean

# View service status
ssh <user>@<ip> "sudo systemctl status nginx nginx-rtmp sparrow-processor"

# View logs
ssh <user>@<ip> "sudo journalctl -u nginx-rtmp -f"
ssh <user>@<ip> "sudo journalctl -u sparrow-processor -f"
```
