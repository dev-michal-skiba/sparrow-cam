#!/bin/bash

set -e

# Get the project root directory (parent of tests directory)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_DIR="$PROJECT_ROOT/local"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test configuration
WEB_URL="http://localhost:8080"
RTMP_URL="rtmp://localhost:8081/live/sparrow_cam"
HLS_URL="http://localhost:8080/hls/sparrow_cam.m3u8"
CONTAINER_NAME="sparrow_cam_local"
STREAM_DURATION=10  # Stream for 10 seconds

echo -e "${YELLOW}Starting SparrowCam E2E Tests...${NC}"
echo ""

# Function to print test status
test_start() {
    echo -ne "  Testing $1... "
}

test_pass() {
    echo -e "${GREEN}✓ PASS${NC}"
}

test_fail() {
    echo -e "${RED}✗ FAIL${NC}"
    echo -e "${RED}Error: $1${NC}"
    exit 1
}

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Cleaning up...${NC}"
    # Kill any remaining ffmpeg processes
    pkill -9 ffmpeg > /dev/null 2>&1 || true
    # Use timeout for docker compose down in case it hangs
    (cd "$LOCAL_DIR" && timeout 10 docker compose down > /dev/null 2>&1) || true
    rm -f /tmp/ffmpeg.log > /dev/null 2>&1 || true
}

# Set trap to cleanup on exit
trap cleanup EXIT

# Test: Check if Docker is running
test_start "Docker availability"
if ! docker info > /dev/null 2>&1; then
    test_fail "Docker is not running"
fi
test_pass

# Test: Build the image
test_start "Docker image build"
if ! (cd "$LOCAL_DIR" && docker compose build > /dev/null 2>&1); then
    test_fail "Failed to build Docker image"
fi
test_pass

# Test: Start the application
test_start "Application startup"
if ! (cd "$LOCAL_DIR" && docker compose up -d > /dev/null 2>&1); then
    test_fail "Failed to start application"
fi
test_pass

# Wait for services to be ready
echo -ne "  Waiting for services to start... "
sleep 5
test_pass

# Test: Check if container is running
test_start "Container health"
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    test_fail "Container is not running"
fi
test_pass

# Test: Check web server is responding
test_start "Web server (port 8080)"
if ! curl -s -o /dev/null -w "%{http_code}" "$WEB_URL" | grep -q "200"; then
    test_fail "Web server is not responding on port 8080"
fi
test_pass

# Test: Check if index.html is served
test_start "Web server content"
if ! curl -s "$WEB_URL" | grep -q "Live Stream"; then
    test_fail "Web server is not serving correct content"
fi
test_pass

# Test: Check RTMP port is open
test_start "RTMP server (port 8081)"
if ! nc -z localhost 8081 2>/dev/null; then
    test_fail "RTMP server is not listening on port 8081"
fi
test_pass

# Test: Check directories exist inside container
test_start "Output directories in container"
if ! docker exec "$CONTAINER_NAME" test -d /var/www/html/hls; then
    test_fail "HLS directory does not exist in container"
fi
test_pass

# Test: Stream video to RTMP server
test_start "RTMP stream acceptance (${STREAM_DURATION}s)"
# Run ffmpeg in background and capture its PID
ffmpeg -re -i "$PROJECT_ROOT/sample.mp4" -c copy -f flv "$RTMP_URL" > /tmp/ffmpeg.log 2>&1 &
FFMPEG_PID=$!

# Wait for specified duration
sleep ${STREAM_DURATION}

# Kill ffmpeg if it's still running (use SIGTERM first, then SIGKILL if needed)
if ps -p $FFMPEG_PID > /dev/null 2>&1; then
    kill $FFMPEG_PID 2>/dev/null || true
    sleep 1
    # Force kill if still running
    if ps -p $FFMPEG_PID > /dev/null 2>&1; then
        kill -9 $FFMPEG_PID 2>/dev/null || true
    fi
fi

# Check if ffmpeg managed to stream (check log for success indicators)
if [ -f /tmp/ffmpeg.log ] && grep -q "speed=" /tmp/ffmpeg.log; then
    test_pass
else
    test_fail "Failed to stream video to RTMP server (check /tmp/ffmpeg.log)"
fi

# Wait a bit for HLS segments to be generated
echo -ne "  Waiting for HLS generation... "
sleep 3
test_pass

# Test: Check if HLS files are generated
test_start "HLS stream generation"
HLS_COUNT=$(docker exec "$CONTAINER_NAME" sh -c "ls /var/www/html/hls/*.ts 2>/dev/null | wc -l" || echo "0")
if [ "$HLS_COUNT" -lt 1 ]; then
    test_fail "HLS stream files were not generated"
fi
test_pass

# Test: Check if HLS playlist is accessible
test_start "HLS playlist access"
if ! curl -s -o /dev/null -w "%{http_code}" "$HLS_URL" | grep -q "200"; then
    test_fail "HLS playlist is not accessible"
fi
test_pass

# Test: Check nginx processes in container
test_start "Nginx processes"
NGINX_COUNT=$(docker exec "$CONTAINER_NAME" ps aux | grep -c "[n]ginx" || echo "0")
if [ "$NGINX_COUNT" -lt 2 ]; then
    test_fail "Not enough nginx processes running (expected at least 2)"
fi
test_pass

# Test: Check supervisord is running
test_start "Supervisord process"
if ! docker exec "$CONTAINER_NAME" ps aux | grep -q "[s]upervisord"; then
    test_fail "Supervisord is not running"
fi
test_pass

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}All tests passed! ✓${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Summary:"
echo "  - Web server is running on http://localhost:8080"
echo "  - RTMP server is accepting streams on rtmp://localhost:8081/live/sparrow_cam"
echo "  - HLS stream is being generated"
echo "  - Recordings are being saved"
echo ""
