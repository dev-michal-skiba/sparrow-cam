# Overview
- Software: Bash script running ffmpeg
- Responsibility: Captures USB webcam feed and produces HLS segments and playlist for the web server to serve. Runs as a systemd service with automatic restart on failure.

## Package Layout
- `app/stream/` — root
    - `stream.sh` — ffmpeg command with backoff retry loop (10s → 30s → 60s+)

## How It Works
1. `stream.sh` runs ffmpeg in a `while true` loop
2. If ffmpeg exits (for any reason), the script logs the failure and sleeps before retrying
3. Retry delays: 10s (1st retry), 30s (2nd retry), 60s (3rd and subsequent retries)
4. The systemd service (`sparrow-stream`) provides an additional safety net — it restarts the script if it crashes unexpectedly

## ffmpeg Command
- Input: `/dev/video0` (USB webcam, MJPEG format, 1920×1080)
- Filter: 8 FPS, center-cropped to 960×540
- Output: HLS segments at `/var/www/html/hls/` (1s segments, rolling window of 60)
- Codec: libx264, ultrafast preset, zerolatency tune

### Changing Frames Per Segment
Segments start on keyframes; FPS and keyframe interval must match segment duration:
- `fps=N`, `-g N`, `-keyint_min N` for 1-second segments at N FPS

## Deployment
- Deployed via `infra/ansible/setup_stream.yml` (see Infra context for details)
- Runs as `sparrow_cam_app` user (in `video` group for camera access)
- Stream files served from `/var/www/html/hls/` (group `sparrow_cam`, mode `0775`)
- The playbook does a sparse git clone of the repo (only `app/stream/`) and symlinks it to `/opt/sparrow_cam_app/apps/stream`
- To deploy changes to `stream.sh`: run `make -C infra setup_stream`

## Formatting, Linting, and Unit Tests
These steps should be skipped — Stream has no formatting, linting, or unit test tooling.
