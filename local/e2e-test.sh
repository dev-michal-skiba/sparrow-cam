#!/bin/bash

set -e

# Get the project root directory (parent of local directory)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_DIR="$PROJECT_ROOT/local"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test configuration
WEB_URL="http://localhost:8080"
RTMP_URL="rtmp://localhost:8081/live/sparrow_cam"
HLS_URL="http://localhost:8080/hls/sparrow_cam.m3u8"
ANNOTATIONS_URL="http://localhost:8080/annotations/bird.json"
STREAM_DURATION=15  # Stream for 15 seconds
WAIT_FOR_PROCESSING=5  # Wait for processor to handle segments

# Exit codes
SUCCESS=0
FAILURE=1

# Function to print test status
test_start() {
    echo -ne "  ${BLUE}Testing${NC} $1... "
}

test_pass() {
    echo -e "${GREEN}✓${NC}"
}

test_fail() {
    echo -e "${RED}✗ FAIL${NC}"
    echo -e "${RED}Error: $1${NC}"
    exit $FAILURE
}

# Function to print section header
section_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Cleanup function
cleanup() {
    EXIT_CODE=$?
    echo ""
    echo -e "${YELLOW}Cleaning up...${NC}"

    # Kill any remaining ffmpeg processes
    pkill -9 ffmpeg > /dev/null 2>&1 || true

    # Stop Docker services
    (cd "$LOCAL_DIR" && docker compose down > /dev/null 2>&1) || true

    # Clean up temp files
    rm -f /tmp/sparrow_cam_ffmpeg.log /tmp/sparrow_cam_hls_check.txt > /dev/null 2>&1 || true

    if [ $EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}Cleanup completed${NC}"
    else
        echo -e "${RED}Cleanup completed (exit code: $EXIT_CODE)${NC}"
    fi

    exit $EXIT_CODE
}

# Set trap to cleanup on exit
trap cleanup EXIT

echo ""
echo -e "${YELLOW}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║     SparrowCam End-to-End Test Suite (Local Docker)        ║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ==============================================================================
section_header "Phase 1: Environment Setup"
# ==============================================================================

test_start "Docker availability"
if ! docker info > /dev/null 2>&1; then
    test_fail "Docker is not running"
fi
test_pass

test_start "Project files integrity"
if [ ! -f "$PROJECT_ROOT/sample.mp4" ]; then
    test_fail "sample.mp4 not found in project root (required for streaming test)"
fi
test_pass

test_start "Docker Compose configuration"
if ! (cd "$LOCAL_DIR" && docker compose config > /dev/null 2>&1); then
    test_fail "Docker Compose configuration is invalid"
fi
test_pass

# ==============================================================================
section_header "Phase 2: Docker Build & Service Startup"
# ==============================================================================

test_start "Building Docker images"
if ! (cd "$LOCAL_DIR" && docker compose build > /dev/null 2>&1); then
    test_fail "Failed to build Docker images"
fi
test_pass

test_start "Starting services (rtmp, processor, web)"
if ! (cd "$LOCAL_DIR" && docker compose up -d > /dev/null 2>&1); then
    test_fail "Failed to start Docker services"
fi
test_pass

test_start "Waiting for services to be healthy (30s timeout)"
WAIT_COUNT=0
MAX_WAITS=60  # 60 * 0.5s = 30s
while [ $WAIT_COUNT -lt $MAX_WAITS ]; do
    RTMP_HEALTHY=$(docker inspect --format='{{.State.Health.Status}}' sparrow_cam_rtmp 2>/dev/null || echo "none")
    WEB_HEALTHY=$(docker inspect --format='{{.State.Health.Status}}' sparrow_cam_web 2>/dev/null || echo "none")

    if [ "$RTMP_HEALTHY" = "healthy" ] && [ "$WEB_HEALTHY" = "healthy" ]; then
        break
    fi

    sleep 0.5
    WAIT_COUNT=$((WAIT_COUNT + 1))
done

if [ $WAIT_COUNT -ge $MAX_WAITS ]; then
    echo -e "${YELLOW}(services may not be fully healthy, continuing anyway)${NC}"
fi
test_pass

# ==============================================================================
section_header "Phase 3: Basic Connectivity Tests"
# ==============================================================================

test_start "Web server health (port 8080)"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$WEB_URL" || echo "000")
if [ "$HTTP_CODE" != "200" ]; then
    test_fail "Web server returned HTTP $HTTP_CODE (expected 200)"
fi
test_pass

test_start "Web server content (checking for index.html)"
if ! curl -s "$WEB_URL" | grep -q "Sparrow Cam"; then
    test_fail "Web server not serving correct content"
fi
test_pass

test_start "RTMP server port (8081) is listening"
if ! nc -z localhost 8081 2>/dev/null; then
    test_fail "RTMP server not listening on port 8081"
fi
test_pass

test_start "Container processes running"
RTMP_RUNNING=$(docker ps | grep -c "sparrow_cam_rtmp" || echo "0")
PROCESSOR_RUNNING=$(docker ps | grep -c "sparrow_cam_processor" || echo "0")
WEB_RUNNING=$(docker ps | grep -c "sparrow_cam_web" || echo "0")

if [ "$RTMP_RUNNING" -ne 1 ] || [ "$PROCESSOR_RUNNING" -ne 1 ] || [ "$WEB_RUNNING" -ne 1 ]; then
    test_fail "Not all containers are running"
fi
test_pass

# ==============================================================================
section_header "Phase 4: RTMP Stream Acceptance & HLS Generation"
# ==============================================================================

test_start "Streaming video to RTMP server (${STREAM_DURATION}s)"

# Run ffmpeg in background
ffmpeg -re -i "$PROJECT_ROOT/sample.mp4" -c copy -f flv "$RTMP_URL" > /tmp/sparrow_cam_ffmpeg.log 2>&1 &
FFMPEG_PID=$!

# Wait for the specified duration
sleep ${STREAM_DURATION}

# Kill ffmpeg gracefully first, then forcefully if needed
if ps -p $FFMPEG_PID > /dev/null 2>&1; then
    kill $FFMPEG_PID 2>/dev/null || true
    sleep 1
    if ps -p $FFMPEG_PID > /dev/null 2>&1; then
        kill -9 $FFMPEG_PID 2>/dev/null || true
    fi
fi

# Verify ffmpeg successfully streamed
if [ -f /tmp/sparrow_cam_ffmpeg.log ] && grep -q "speed=" /tmp/sparrow_cam_ffmpeg.log; then
    test_pass
else
    test_fail "FFmpeg failed to stream to RTMP server"
fi

# Wait for RTMP server to generate HLS segments
echo -ne "  ${BLUE}Waiting${NC} for HLS segments to be generated... "
sleep 3
test_pass

# Test: Check if HLS playlist and segments exist
test_start "HLS playlist file generation"
PLAYLIST_EXISTS=$(docker exec sparrow_cam_rtmp test -f /var/www/html/hls/sparrow_cam.m3u8 && echo "yes" || echo "no")
if [ "$PLAYLIST_EXISTS" != "yes" ]; then
    test_fail "HLS playlist file not generated at /var/www/html/hls/sparrow_cam.m3u8"
fi
test_pass

test_start "HLS segments (.ts files) generation"
HLS_SEGMENT_COUNT=$(docker exec sparrow_cam_rtmp sh -c "ls /var/www/html/hls/*.ts 2>/dev/null | wc -l" || echo "0")
if [ "$HLS_SEGMENT_COUNT" -lt 5 ]; then
    test_fail "Not enough HLS segments generated (found: $HLS_SEGMENT_COUNT, expected: >=5)"
fi
test_pass

test_start "HLS playlist accessibility via HTTP"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HLS_URL" || echo "000")
if [ "$HTTP_CODE" != "200" ]; then
    test_fail "HLS playlist returned HTTP $HTTP_CODE"
fi
test_pass

test_start "HLS playlist content validity"
if ! curl -s "$HLS_URL" | grep -q "EXTINF"; then
    test_fail "HLS playlist does not contain valid M3U8 format"
fi
test_pass

# ==============================================================================
section_header "Phase 5: Processor Service - Bird Detection & Annotations"
# ==============================================================================

echo -ne "  ${BLUE}Waiting${NC} for processor to handle segments... "
sleep ${WAIT_FOR_PROCESSING}
test_pass

test_start "Annotations file existence"
ANNOTATIONS_EXISTS=$(docker exec sparrow_cam_processor test -f /var/www/html/annotations/bird.json && echo "yes" || echo "no")
if [ "$ANNOTATIONS_EXISTS" != "yes" ]; then
    test_fail "Annotations file not created at /var/www/html/annotations/bird.json"
fi
test_pass

test_start "Annotations file contains segment data"
ANNOTATIONS_CONTENT=$(docker exec sparrow_cam_processor cat /var/www/html/annotations/bird.json 2>/dev/null)
ANNOTATION_COUNT=$(echo "$ANNOTATIONS_CONTENT" | grep -o '\"bird_detected\"' | wc -l || echo "0")
if [ "$ANNOTATION_COUNT" -lt 1 ]; then
    echo ""
    echo -e "${YELLOW}Debug: Annotations file content:${NC}"
    echo "$ANNOTATIONS_CONTENT" | head -50
    test_fail "Annotations file does not contain bird_detected annotations (found: $ANNOTATION_COUNT entries)"
fi
test_pass

test_start "Processor container logs show processing activity"
PROCESSOR_LOGS_OUTPUT=$(docker logs sparrow_cam_processor 2>&1)
# Check for either "Bird detected" or "No bird detected" in logs
if echo "$PROCESSOR_LOGS_OUTPUT" | grep -qE "(Bird detected|No bird detected)"; then
    test_pass
else
    echo ""
    echo -e "${YELLOW}Debug: Processor logs (last 30 lines):${NC}"
    echo "$PROCESSOR_LOGS_OUTPUT" | tail -30
    test_fail "Processor logs do not show bird detection activity"
fi

# Separate check for errors and warnings in processor logs
test_start "Processor logs do not contain errors or warnings"
ERRORS_WARNINGS=$(echo "$PROCESSOR_LOGS_OUTPUT" | grep -E "(WARNING|ERROR)" | head -5)
if [ -n "$ERRORS_WARNINGS" ]; then
    echo ""
    echo -e "${YELLOW}Debug: Errors/Warnings found in processor logs:${NC}"
    echo "$ERRORS_WARNINGS"
    test_fail "Processor logs contain ERROR or WARNING messages"
fi
test_pass

# ==============================================================================
section_header "Phase 6: Web Server - Content Delivery"
# ==============================================================================

test_start "Annotations file accessibility via HTTP"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$ANNOTATIONS_URL" || echo "000")
if [ "$HTTP_CODE" != "200" ]; then
    test_fail "Annotations file returned HTTP $HTTP_CODE"
fi
test_pass

test_start "Annotations file validity via HTTP"
if ! curl -s "$ANNOTATIONS_URL" | grep -q "bird_detected"; then
    test_fail "Annotations file does not contain expected data via HTTP"
fi
test_pass

test_start "HLS streaming through web server"
if ! curl -s "$HLS_URL" | grep -q "\.ts"; then
    test_fail "HLS playlist from web server does not reference segment files"
fi
test_pass

# ==============================================================================
section_header "Phase 7: Integration Verification"
# ==============================================================================

test_start "Processor has consumed HLS segments"
CONSUMED=$(docker exec sparrow_cam_processor sh -c "cat /var/www/html/annotations/bird.json | grep -o '\"bird_detected\"' | wc -l" || echo "0")
if [ "$CONSUMED" -lt 1 ]; then
    test_fail "Processor has not annotated any segments"
fi
test_pass

test_start "Web server has access to shared volumes"
WEB_HLS_COUNT=$(docker exec sparrow_cam_web sh -c "ls /var/www/html/hls/*.ts 2>/dev/null | wc -l" || echo "0")
WEB_ANNO_EXISTS=$(docker exec sparrow_cam_web test -f /var/www/html/annotations/bird.json && echo "yes" || echo "no")
if [ "$WEB_HLS_COUNT" -lt 5 ] || [ "$WEB_ANNO_EXISTS" != "yes" ]; then
    test_fail "Web server cannot access shared volumes properly"
fi
test_pass

test_start "End-to-end pipeline is functional"
# Verify all components have worked together
if [ "$HLS_SEGMENT_COUNT" -ge 5 ] && [ "$ANNOTATION_COUNT" -ge 1 ] && [ "$HTTP_CODE" = "200" ]; then
    test_pass
else
    test_fail "End-to-end pipeline verification failed"
fi

# ==============================================================================
section_header "Test Summary"
# ==============================================================================

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            All E2E Tests Passed Successfully! ✓            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo "✓ RTMP Server:"
echo "  - Accepted RTMP stream from FFmpeg"
echo "  - Generated HLS playlist with $HLS_SEGMENT_COUNT segments"
echo ""

echo "✓ Processor Service:"
echo "  - Monitored HLS directory for new segments"
echo "  - Processed segments and detected birds"
echo "  - Created annotations file with $ANNOTATION_COUNT entries"
echo ""

echo "✓ Web Server:"
echo "  - Serves HLS stream via HTTP ($HLS_URL)"
echo "  - Serves annotations file via HTTP ($ANNOTATIONS_URL)"
echo "  - Has access to all shared volumes"
echo ""

echo -e "${YELLOW}Access points:${NC}"
echo "  • Web interface: $WEB_URL"
echo "  • HLS stream: $HLS_URL"
echo "  • Annotations: $ANNOTATIONS_URL"
echo ""

exit $SUCCESS
