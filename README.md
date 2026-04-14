# SparrowCam

Local bird feeder observation system. Monitors camera feed, automatically detects birds, archives and streams video. Runs entirely on your home network.

## Features

- Local-first (no cloud dependency)
- Automatic bird detection via YOLOv8
- Real-time HLS video streaming
- Web interface on your local network
- Live bird detection status display

## Project Structure

- **`agent_docs/`** - Documentation for AI agents
- **`app/`** - Apps source code
- **`infra/`** - Infrastructure deployment to Raspberry Pi
- **`local/`** - Local development environment

See individual README files for details.

## Quick Start

### Local Development

```bash
make -C local build
make -C local start
make -C local stop

# Access: http://localhost:8080
```

See [local/README.md](local/README.md)

### Deploy to Raspberry Pi

See [infra/README.md](infra/README.md)
