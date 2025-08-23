# SparrowCam

Local bird feeder observation system that runs entirely on your home network.

## Overview
SparrowCam monitors a bird feeder using a connected camera. It runs on a local server and is reachable from devices on your Wi‑Fi network. The system continuously watches the camera feed and automatically records short video clips when birds are detected. All videos are stored locally.

## Features
- Local-first operation: runs on a local server with no cloud dependency
- LAN access: available to devices connected to your home Wi‑Fi
- Continuous monitoring: watches the camera feed throughout the day
- Automatic detection: starts recording when a bird is detected
- Local storage: saves recorded clips on the local server

## How it works
1. The application continuously processes the camera feed.
2. When birds are detected (e.g., via motion/object detection), it starts recording.
3. Recorded clips are saved locally, typically with timestamps for easy browsing.
4. A simple web interface is exposed on your local network.
