# Testing

End-to-end tests that verify the full system functionality.

## Quick Start

```bash
# Run all tests
make -C tests e2e
```

Tests verify:
- Docker build and startup
- Web server (port 8080)
- RTMP server (port 8081)
- HLS stream generation
- Recording functionality
- Process management

Tests automatically build, start, test, and clean up.

## Troubleshooting

```bash
# View test logs
cat /tmp/ffmpeg.log

# Check container
docker logs sparrow_cam_local

# Clean up manually
docker rm -f sparrow_cam_local
```
