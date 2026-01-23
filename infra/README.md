# Infrastructure

Ansible-based infrastructure deployment to Raspberry Pi or similar devices.

## Prerequisites

- Target device: Raspberry Pi with Ubuntu Server 25.04
- SSH access configured
- Same local network as development machine
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

After deploying with `make -C infra setup_all`, start the ffmpeg stream in a tmux session on the target device:

```bash
ffmpeg \
   -f v4l2
   -input_format mjpeg
   -video_size 1920x1080
   -i /dev/video0
   -vf "fps=8,crop=iw/2:ih/2:(iw-iw/2)/2:(ih-ih/2)/2"
   -c:v libx264
   -preset ultrafast
   -tune zerolatency
   -g 24
   -pix_fmt yuv420p
   -an
   -f hls
   -hls_time 1
   -hls_list_size 60
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
   - Runs in tmux session
   - Captures video from `/dev/video0` and converts to HLS segments
   - Outputs segments to `/var/www/html/hls/`
   - Started manually in tmux on the target device
