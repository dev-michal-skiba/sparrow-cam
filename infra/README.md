# Infrastructure

Ansible-based infrastructure deployment to Raspberry Pi 5 or similar.

## Prerequisites

- Target device: Raspberry Pi 5 with Raspberry Pi OS Lite (64-bit) or similar
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

**Step 2: Flash OS with Raspberry Pi Imager**

Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/) to flash the OS. In the OS customisation settings:
- Set a username (e.g. `sparrow_cam_infra`) and password
- Enable SSH and add your public key under "Allow public-key authentication only"

This creates the user and sets up SSH key access automatically.

**Step 3: Configure Ansible variables**

```bash
# Copy example vars and update with your values
cp infra/ansible/group_vars/all.yml.example infra/ansible/group_vars/all.yml
# Edit all.yml with your target IP and username
```

## Deploy

```bash
# [OPTIONAL]  Build infrastructure docker container
make -C infra build

# [OPTIONAL]  Test connection
make -C infra ping

make -C infra setup_users       # Setup users, groups, and passwordless sudo
make -C infra setup_storage     # Mount external hard drive
make -C infra setup_processor   # Processor service
make -C infra setup_archive_api # Archive API service (port 5001, proxied via nginx)
make -C infra setup_stream      # Stream service (ffmpeg HLS stream)
make -C infra setup_web         # Web server (port 80)
```

## Stream Service

The stream is managed by the `sparrow-stream` systemd service, deployed via `make -C infra setup_stream`. It starts automatically on boot and restarts ffmpeg on failure with a backoff retry (10s → 30s → 60s+).

```bash
# Check stream service status
sudo systemctl status sparrow-stream

# View stream logs
journalctl -u sparrow-stream -f
```

### Changing frames per segment

Segments start on keyframes, so the frame rate and keyframe interval must match the segment duration.

Use the formula:

frames_per_segment = fps × segment_duration
g = keyint_min = frames_per_segment

Example (1s segments at 8 FPS):

- `fps=8`
- `-g 8`
- `-keyint_min 8`

Update `app/stream/stream.sh` then re-run `make -C infra setup_stream` to deploy changes.

## Usage

**Access** (replace with your Pi's IP):
- Web: http://192.168.1.100/

## Journal Logs

> **Note:** To read logs without `sudo`, add your user to the `systemd-journal` group and re-login:
> ```bash
> sudo usermod -aG systemd-journal <your-user>
> ```

```bash
# Live tail processor logs
journalctl -u sparrow-processor -f

# Live tail stream logs
journalctl -u sparrow-stream -f

# Show last 100 lines
journalctl -u sparrow-processor -n 100

# Filter by date range
journalctl -u sparrow-processor --since "2026-03-03" --until "2026-03-04"
journalctl -u sparrow-processor --since "2026-03-07 13:15:35" --until "2026-03-07 13:15:55"
journalctl -u sparrow-processor --since "today"
journalctl -u sparrow-processor --since "1 hour ago"
journalctl -u sparrow-processor --since "5 seconds ago"

# Search for a phrase (pipe through grep)
journalctl -u sparrow-processor --no-pager | grep "Bird detected"

# Check total disk usage of all journal logs
journalctl --disk-usage
```

