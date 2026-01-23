# Deployment

Ansible-based deployment to Raspberry Pi or similar devices.

## Prerequisites

- Target device: Raspberry Pi with Ubuntu Server 25.04
- SSH access configured
- Same local network as development machine
```

## Deploy

```bash
# Build deployment docker container
make -C deploy build

# Test connection
make -C deploy ping

# Deploy web, processor, and other core services
make -C deploy all

# Or deploy separately
make -C deploy users     # Setup users and groups
make -C deploy mount     # Mount external hard drive
make -C deploy processor # Processor service
make -C deploy web       # Web server (port 80)
```

## Starting the Stream

After deploying with `make -C deploy all`, start the ffmpeg stream in a tmux session on the target device:

```bash
ffmpeg \
  -f v4l2 \
  -input_format mjpeg \
  -video_size 1920x1080 \
  -i /dev/video0 \
  -vf "scale=iw/2:ih/2" \
  -r 8 \
  -c:v libx264 \
  -preset ultrafast \
  -tune zerolatency \
  -g 24 \
  -f hls \
  -hls_time 1 \
  -hls_list_size 60 \
  /var/www/html/hls/sparrow_cam.m3u8
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
