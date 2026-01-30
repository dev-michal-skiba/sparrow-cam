# Infrastructure

Ansible-based infrastructure deployment to Raspberry Pi or similar devices.

## Prerequisites

- Target device: Raspberry Pi with Ubuntu Server 25.04
- Same local network as development machine

### Target User Setup (sparrow_cam_infra)

Ansible requires an SSH user on the target device with sudo privileges.

**Step 1: Generate SSH key on dev machine**

```bash
# Generate SSH key pair (run on your development machine)
ssh-keygen -t ed25519 -f infra/ansible/ssh_key -C "sparrow_cam_infra"

# This creates:
#   infra/ansible/ssh_key      (private key - used by Ansible)
#   infra/ansible/ssh_key.pub  (public key - copy to target)
```

**Step 2: Create user on target device**

```bash
# On target device (as root or existing sudo user)
sudo adduser sparrow_cam_infra
sudo usermod -aG sudo sparrow_cam_infra

# Add to sparrow_cam_processor group for access to archive storage
sudo usermod -aG sparrow_cam_processor sparrow_cam_infra

# Enable passwordless sudo
echo "sparrow_cam_infra ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/sparrow_cam_infra
```

**Step 3: Copy public key to target**

```bash
# Option A: Using ssh-copy-id (requires password auth enabled temporarily)
ssh-copy-id -i infra/ansible/ssh_key.pub sparrow_cam_infra@<target-ip>

# Option B: Manual copy (if password auth disabled)
# On target device:
sudo -u sparrow_cam_infra mkdir -p /home/sparrow_cam_infra/.ssh
sudo -u sparrow_cam_infra chmod 700 /home/sparrow_cam_infra/.ssh
echo "<contents of ssh_key.pub>" | sudo -u sparrow_cam_infra tee /home/sparrow_cam_infra/.ssh/authorized_keys
sudo -u sparrow_cam_infra chmod 600 /home/sparrow_cam_infra/.ssh/authorized_keys
```

**Step 4: Configure Ansible variables**

```bash
# Copy example vars and update with your values
cp infra/ansible/group_vars/all.yml.example infra/ansible/group_vars/all.yml
# Edit all.yml with your target IP and username
```

## Deploy

```bash
# Build infrastructure docker container
make -C infra build

# Test connection
make -C infra ping

# Deploy web, processor, and other core services
make -C infra setup_all

# Or deploy separately
make -C infra setup_users     # Setup users and groups
make -C infra setup_storage   # Mount external hard drive
make -C infra setup_processor # Processor service
make -C infra setup_web       # Web server (port 80)
```

## Starting the Stream

After deploying with `make -C infra setup_all`, start the ffmpeg stream on the target device.

**Important:** Run ffmpeg as the `sparrow_cam_stream` user to ensure proper write permissions to the HLS directory.

```bash
# Switch to the stream user
sudo -u sparrow_cam_stream -i

# Start tmux session
tmux

# Run ffmpeg
ffmpeg \
   -f v4l2 \
   -input_format mjpeg \
   -video_size 1920x1080 \
   -i /dev/video0 \
   -vf "fps=8,crop=iw/2:ih/2:(iw-iw/2)/2:(ih-ih/2)/2" \
   -c:v libx264 \
   -preset ultrafast \
   -tune zerolatency \
   -g 24 \
   -pix_fmt yuv420p \
   -an \
   -f hls \
   -hls_time 1 \
   -hls_list_size 60 \
   -hls_flags delete_segments+append_list \
   -hls_segment_filename "/var/www/html/hls/sparrow_cam-%d.ts" /var/www/html/hls/sparrow_cam.m3u8
```

## Usage

**Access** (replace with your Pi's IP):
- Web: http://192.168.1.100/

## Service Architecture

The deployment creates two systemd services on the target device, plus a manual ffmpeg stream:

1. **nginx** (port 80) - Web server
   - Serves web interface and HLS streams
   - Hosts annotation file from processor (`/var/www/html/annotations/bird.json`)
   - Configuration: `/etc/nginx/nginx.conf`

2. **sparrow-processor** - HLS segment processor
   - Monitors `/var/www/html/hls` for new segments
   - Processes each frame and detects birds
   - Outputs annotations to `/var/www/html/annotations/bird.json`
   - Runs as `sparrow_cam_processor` user

3. **ffmpeg stream** (tmux session) - USB camera to HLS
   - Runs in tmux session as `sparrow_cam_stream` user
   - Captures video from `/dev/video0` and converts to HLS segments
   - Outputs segments to `/var/www/html/hls/`
   - Started manually in tmux on the target device
