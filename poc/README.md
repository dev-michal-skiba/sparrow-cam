# SparrowCam POC

A minimal proof-of-concept that simulates a webcam feed, processes it, and serves a live MJPEG stream via a simple web UI.

## How to Run
- Prerequisites
    - Docker
    - Docker Compose
- Run
    - `docker compose up --build`
- Open the UI at [http://localhost:8081](http://localhost:8081).

## What You’ll See
- A looping sample video streams via RTMP.
- The processor applies a subtle overlay (a small green box with text) to indicate processing.
- The web page displays the processed MJPEG stream.

## Architecture
- rtmp-server: NGINX RTMP server (port 1935) for ingesting RTMP.
- stream: ffmpeg loops `sample.mp4` and pushes RTMP to `rtmp://rtmp-server:1935/stream/sparrow_cam` (acts as a webcam mock).
- processor: Python + OpenCV reads RTMP, overlays a subtle indicator, exposes:
  - `/mjpeg` (MJPEG stream).
  - `/health` (health check).
- web: NGINX serves the UI and proxies `/api/*` to the processor.
