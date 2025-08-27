# SparrowCam POC

A minimal proof-of-concept that simulates a webcam feed, processes it, and serves a live MJPEG stream via a simple web UI.

## How to Run
- Prerequisites
    - Docker
    - Docker Compose
- Build
    - `docker compose build`
- Run
    - `docker compose up`
- Open the UI at [http://localhost:8081](http://localhost:8081).

## What You'll See
- A looping sample video streams via RTMP.
- The processor runs real-time bird detection using YOLOv8n model.
- When birds are detected (every 12th frame), a green "Birds detected" status appears in the top-right corner.
- The status persists for 5 seconds after detection, and each new bird detection extends it by another 5 seconds.
- The web page displays the processed MJPEG stream with live bird detection status.

## Proof of Concept Observations

### Current Implementation
- **Detection frequency**: Every 12th frame (~2.5fps at 30fps stream) to optimize CPU usage
- **Model**: YOLOv8n with COCO dataset (class 14 = birds)
- **Image resolution**: 420px for detection (balance between speed and accuracy)
- **Status duration**: 5 seconds per detection, extensible with new detections
- **Performance**: Optimized for Raspberry Pi deployment with minimal CPU overhead

### Identified Improvements for Production
1. **Model Fine-tuning Required**: The generic COCO model needs fine-tuning for accurate bird detection in crowded birdhouse scenarios and rear-view angles. A custom model will enable reducing the current 5-second status duration for more responsive detection alerts.

## Architecture
- rtmp-server: NGINX RTMP server (port 1935) for ingesting RTMP.
- stream: ffmpeg loops `sample.mp4` and pushes RTMP to `rtmp://rtmp-server:1935/stream/sparrow_cam` (acts as a webcam mock).
- processor: Python + OpenCV reads RTMP, overlays a subtle indicator, exposes:
  - `/mjpeg` (MJPEG stream).
- web: NGINX serves the UI and proxies `/api/*` to the processor.
