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
HLS_URL="http://localhost:8080/hls/sparrow_cam.m3u8"
ANNOTATIONS_URL="http://localhost:8080/annotations/bird.json"
ARCHIVE_API_URL="http://localhost:8080/archive/api"

# Expected counts (based on sample.mp4 — update if sample changes)
EXPECTED_BIRD_DETECTIONS=20  # segments with detections in final annotations file

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

    # Kill ffmpeg process inside processor container
    docker exec sparrow_cam_processor pkill -f "ffmpeg.*sparrow_cam" > /dev/null 2>&1 || true

    # Stop Docker services
    (cd "$LOCAL_DIR" && docker compose down > /dev/null 2>&1) || true

    # Clean up temp files
    rm -f /tmp/sparrow_cam_ffmpeg.log > /dev/null 2>&1 || true

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

test_start "Docker Compose configuration"
if ! (cd "$LOCAL_DIR" && docker compose config > /dev/null 2>&1); then
    test_fail "Docker Compose configuration is invalid"
fi
test_pass

test_start "sample.mp4 exists"
if [ ! -f "$PROJECT_ROOT/sample.mp4" ]; then
    test_fail "sample.mp4 not found at $PROJECT_ROOT/sample.mp4"
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

test_start "Starting services (processor, web)"
if ! (cd "$LOCAL_DIR" && docker compose up -d > /dev/null 2>&1); then
    test_fail "Failed to start Docker services"
fi
test_pass

test_start "Waiting for services to be healthy (30s timeout)"
WAIT_COUNT=0
MAX_WAITS=60  # 60 * 0.5s = 30s
while [ $WAIT_COUNT -lt $MAX_WAITS ]; do
    WEB_HEALTHY=$(docker inspect --format='{{.State.Health.Status}}' sparrow_cam_web 2>/dev/null || echo "none")
    if [ "$WEB_HEALTHY" = "healthy" ]; then
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

test_start "Web server serves Sparrow Cam page"
if ! curl -s "$WEB_URL" | grep -q "Sparrow Cam"; then
    test_fail "Web server not serving correct content"
fi
test_pass

test_start "Container processes running"
PROCESSOR_RUNNING=$(docker ps | grep -c "sparrow_cam_processor" || echo "0")
WEB_RUNNING=$(docker ps | grep -c "sparrow_cam_nginx" || echo "0")
if [ "$PROCESSOR_RUNNING" -ne 1 ] || [ "$WEB_RUNNING" -ne 1 ]; then
    test_fail "Not all containers are running"
fi
test_pass

# ==============================================================================
section_header "Phase 4: HLS Streaming (single pass of sample.mp4)"
# ==============================================================================

test_start "Copying sample.mp4 to processor container"
docker cp "$PROJECT_ROOT/sample.mp4" sparrow_cam_processor:/tmp/sample.mp4
test_pass

test_start "Starting ffmpeg to stream sample.mp4 once as HLS"
# Stream sample.mp4 once (no -stream_loop) with production-matching settings
docker exec -d sparrow_cam_processor ffmpeg \
    -re \
    -i /tmp/sample.mp4 \
    -c:v libx264 \
    -preset ultrafast \
    -g 8 \
    -keyint_min 8 \
    -sc_threshold 0 \
    -pix_fmt yuv420p \
    -an \
    -f hls \
    -hls_time 1 \
    -hls_list_size 60 \
    -hls_flags delete_segments+append_list \
    -hls_segment_filename /var/www/html/hls/sparrow_cam-%d.ts \
    /var/www/html/hls/sparrow_cam.m3u8 > /tmp/sparrow_cam_ffmpeg.log 2>&1

# Wait for ffmpeg to start (up to 15s)
WAIT_COUNT=0
MAX_WAITS=30  # 30 * 0.5s = 15s
while [ $WAIT_COUNT -lt $MAX_WAITS ]; do
    if docker exec sparrow_cam_processor pgrep -f "ffmpeg.*sparrow_cam" > /dev/null 2>&1; then
        break
    fi
    sleep 0.5
    WAIT_COUNT=$((WAIT_COUNT + 1))
done
if ! docker exec sparrow_cam_processor pgrep -f "ffmpeg.*sparrow_cam" > /dev/null 2>&1; then
    echo ""
    echo -e "${YELLOW}Debug: ffmpeg startup log:${NC}"
    docker exec sparrow_cam_processor cat /tmp/sparrow_cam_ffmpeg.log || true
    test_fail "ffmpeg failed to start"
fi
test_pass

test_start "Waiting for ffmpeg to finish streaming sample.mp4 (up to 240s)"
WAIT_COUNT=0
MAX_WAITS=480  # 480 * 0.5s = 240s
while [ $WAIT_COUNT -lt $MAX_WAITS ]; do
    if ! docker exec sparrow_cam_processor pgrep -f "ffmpeg.*sparrow_cam" > /dev/null 2>&1; then
        break
    fi
    sleep 0.5
    WAIT_COUNT=$((WAIT_COUNT + 1))
done
if docker exec sparrow_cam_processor pgrep -f "ffmpeg.*sparrow_cam" > /dev/null 2>&1; then
    test_fail "ffmpeg did not finish within 240s"
fi
test_pass

test_start "HLS segments (.ts files) created in shared volume"
TOTAL_SEGMENTS=$(docker exec sparrow_cam_processor sh -c "ls /var/www/html/hls/*.ts 2>/dev/null | wc -l" || echo "0")
if [ "$TOTAL_SEGMENTS" -lt 1 ]; then
    echo ""
    echo -e "${YELLOW}Debug: ffmpeg log:${NC}"
    docker exec sparrow_cam_processor cat /tmp/sparrow_cam_ffmpeg.log || true
    test_fail "No HLS segments found after ffmpeg completed"
fi
echo -ne "(${TOTAL_SEGMENTS} segments) "
test_pass

test_start "HLS playlist accessible via HTTP"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HLS_URL" || echo "000")
if [ "$HTTP_CODE" != "200" ]; then
    test_fail "HLS playlist returned HTTP $HTTP_CODE"
fi
test_pass

test_start "HLS playlist contains valid M3U8 content"
if ! curl -s "$HLS_URL" | grep -q "EXTINF"; then
    test_fail "HLS playlist does not contain valid M3U8 format"
fi
test_pass

# ==============================================================================
section_header "Phase 5: Processor - Bird Detection & Annotations"
# ==============================================================================

test_start "Waiting for processor to annotate all segments (up to 60s)"
# Poll until annotation count stabilizes (no change for 3 consecutive seconds)
PREV_COUNT=-1
STABLE_TICKS=0
WAIT_COUNT=0
MAX_WAITS=120  # 120 * 0.5s = 60s
while [ $WAIT_COUNT -lt $MAX_WAITS ]; do
    ANNOTATION_COUNT=$(docker exec sparrow_cam_processor python3 -c "
import json
try:
    with open('/var/www/html/annotations/bird.json') as f:
        data = json.load(f)
    print(len(data.get('detections', {})))
except Exception:
    print(0)
" 2>/dev/null || echo "0")
    ANNOTATION_COUNT=$((ANNOTATION_COUNT + 0))  # ensure numeric
    if [ "$ANNOTATION_COUNT" -eq "$PREV_COUNT" ] && [ "$ANNOTATION_COUNT" -gt 0 ]; then
        STABLE_TICKS=$((STABLE_TICKS + 1))
        if [ $STABLE_TICKS -ge 6 ]; then  # stable for 3s
            break
        fi
    else
        STABLE_TICKS=0
        PREV_COUNT=$ANNOTATION_COUNT
    fi
    sleep 0.5
    WAIT_COUNT=$((WAIT_COUNT + 1))
done
if [ "$ANNOTATION_COUNT" -lt 1 ]; then
    test_fail "No annotations produced after waiting 60s"
fi
echo -ne "(${ANNOTATION_COUNT} annotations) "
test_pass

test_start "Annotations file exists"
ANNOTATIONS_EXISTS=$(docker exec sparrow_cam_processor test -f /var/www/html/annotations/bird.json && echo "yes" || echo "no")
if [ "$ANNOTATIONS_EXISTS" != "yes" ]; then
    test_fail "Annotations file not found at /var/www/html/annotations/bird.json"
fi
test_pass

test_start "Annotations contain bird detections (expected >= ${EXPECTED_BIRD_DETECTIONS})"
ANNOTATIONS_CONTENT=$(docker exec sparrow_cam_processor cat /var/www/html/annotations/bird.json 2>/dev/null)
BIRD_DETECTIONS=$(echo "$ANNOTATIONS_CONTENT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(len(data.get('detections', {})))
" 2>/dev/null || echo "0")
if [ "$BIRD_DETECTIONS" -lt "$EXPECTED_BIRD_DETECTIONS" ]; then
    echo ""
    echo -e "${YELLOW}Debug: Annotations file content:${NC}"
    echo "$ANNOTATIONS_CONTENT" | head -50
    test_fail "Expected >= ${EXPECTED_BIRD_DETECTIONS} bird detections, got ${BIRD_DETECTIONS}"
fi
echo -ne "(${BIRD_DETECTIONS} bird detections) "
test_pass

# ==============================================================================
section_header "Phase 6: Processor Logs Verification"
# ==============================================================================

PROCESSOR_LOGS=$(docker logs sparrow_cam_processor 2>&1)

test_start "Processor logs show segment processing"
if ! echo "$PROCESSOR_LOGS" | grep -q "Performance: Processing time:"; then
    echo ""
    echo -e "${YELLOW}Debug: Processor logs (last 30 lines):${NC}"
    echo "$PROCESSOR_LOGS" | tail -30
    test_fail "No 'Performance: Processing time:' in processor logs"
fi
PROCESSING_COUNT=$(echo "$PROCESSOR_LOGS" | grep -c "Performance: Processing time:" || echo "0")
echo -ne "(${PROCESSING_COUNT} segments processed) "
test_pass

test_start "Processor logs show bird detections"
if ! echo "$PROCESSOR_LOGS" | grep -q "'Bird detected'"; then
    echo ""
    echo -e "${YELLOW}Debug: Processor logs (last 30 lines):${NC}"
    echo "$PROCESSOR_LOGS" | tail -30
    test_fail "No 'Bird detected' in processor logs"
fi
DETECTED_LOG_COUNT=$(echo "$PROCESSOR_LOGS" | grep -c "'Bird detected'" || echo "0")
echo -ne "(${DETECTED_LOG_COUNT} detections logged) "
test_pass

test_start "Processor logs show archive scheduling"
if ! echo "$PROCESSOR_LOGS" | grep -q "Bird detected, archive scheduled in"; then
    echo ""
    echo -e "${YELLOW}Debug: Relevant processor log lines:${NC}"
    echo "$PROCESSOR_LOGS" | grep -E "(Bird|archive|Archive)" | head -20
    test_fail "No archive scheduling in processor logs"
fi
test_pass

test_start "Processor logs show archive execution"
if ! echo "$PROCESSOR_LOGS" | grep -q "Executing scheduled archive:"; then
    echo ""
    echo -e "${YELLOW}Debug: Relevant processor log lines:${NC}"
    echo "$PROCESSOR_LOGS" | grep -E "(archive|Archive)" | head -20
    test_fail "No archive execution in processor logs"
fi
ARCHIVE_COUNT=$(echo "$PROCESSOR_LOGS" | grep -c "Executing scheduled archive:" || echo "0")
echo -ne "(${ARCHIVE_COUNT} archives created) "
test_pass

test_start "Processor logs contain no ERROR or WARNING"
ERRORS_WARNINGS=$(echo "$PROCESSOR_LOGS" | grep -E "^.*(WARNING|ERROR)" | head -5)
if [ -n "$ERRORS_WARNINGS" ]; then
    echo ""
    echo -e "${YELLOW}Debug: Errors/Warnings found in processor logs:${NC}"
    echo "$ERRORS_WARNINGS"
    test_fail "Processor logs contain ERROR or WARNING messages"
fi
test_pass

# ==============================================================================
section_header "Phase 7: Web Server & Integration"
# ==============================================================================

test_start "Annotations file accessible via HTTP"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$ANNOTATIONS_URL" || echo "000")
if [ "$HTTP_CODE" != "200" ]; then
    test_fail "Annotations file returned HTTP $HTTP_CODE"
fi
test_pass

test_start "Annotations file contains bird_detected via HTTP"
if ! curl -s "$ANNOTATIONS_URL" | grep -q "detections"; then
    test_fail "Annotations file does not contain expected data via HTTP"
fi
test_pass

test_start "HLS playlist references segment files via HTTP"
if ! curl -s "$HLS_URL" | grep -q "\.ts"; then
    test_fail "HLS playlist from web server does not reference segment files"
fi
test_pass

test_start "Web server has access to shared volumes"
WEB_HLS_COUNT=$(docker exec sparrow_cam_nginx sh -c "ls /var/www/html/hls/*.ts 2>/dev/null | wc -l" || echo "0")
WEB_ANNO_EXISTS=$(docker exec sparrow_cam_nginx test -f /var/www/html/annotations/bird.json && echo "yes" || echo "no")
if [ "$WEB_HLS_COUNT" -lt 1 ] || [ "$WEB_ANNO_EXISTS" != "yes" ]; then
    test_fail "Web server cannot access shared volumes properly (hls_count=$WEB_HLS_COUNT, anno=$WEB_ANNO_EXISTS)"
fi
test_pass

# ==============================================================================
section_header "Phase 8: Archive API"
# ==============================================================================

TODAY=$(date +%Y-%m-%d)

test_start "Archive API container running"
ARCHIVE_API_RUNNING=$(docker ps | grep -c "sparrow_cam_archive_api" || echo "0")
if [ "$ARCHIVE_API_RUNNING" -ne 1 ]; then
    test_fail "archive_api container is not running"
fi
test_pass

test_start "Archive API accessible via HTTP"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$ARCHIVE_API_URL?from=$TODAY&to=$TODAY" || echo "000")
if [ "$HTTP_CODE" != "200" ]; then
    test_fail "Archive API returned HTTP $HTTP_CODE (expected 200)"
fi
test_pass

test_start "Archive API returns valid JSON"
ARCHIVE_RESPONSE=$(curl -s "$ARCHIVE_API_URL?from=$TODAY&to=$TODAY" || echo "")
if ! echo "$ARCHIVE_RESPONSE" | python3 -c "import json, sys; json.load(sys.stdin)" 2>/dev/null; then
    test_fail "Archive API response is not valid JSON"
fi
test_pass

test_start "Archive API returns archive data for today"
ARCHIVE_STREAM_COUNT=$(echo "$ARCHIVE_RESPONSE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
count = sum(len(streams) for year in data.values() for month in year.values() for streams in month.values())
print(count)
" 2>/dev/null || echo "0")
if [ "$ARCHIVE_STREAM_COUNT" -lt 1 ]; then
    echo ""
    echo -e "${YELLOW}Debug: Archive API response:${NC}"
    echo "$ARCHIVE_RESPONSE"
    test_fail "Archive API returned no archive streams for today"
fi
echo -ne "(${ARCHIVE_STREAM_COUNT} streams) "
test_pass

# ==============================================================================
section_header "Test Summary"
# ==============================================================================

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            All E2E Tests Passed Successfully! ✓            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo "✓ HLS Stream:"
echo "  - Streamed sample.mp4 as ${TOTAL_SEGMENTS} HLS segments (1s each)"
echo ""

echo "✓ Processor Service:"
echo "  - Processed ${PROCESSING_COUNT} segments"
echo "  - Detected birds in ${BIRD_DETECTIONS} segment(s)"
echo "  - Produced ${ANNOTATION_COUNT} annotation entries"
echo "  - Created ${ARCHIVE_COUNT} archive(s)"
echo ""

echo "✓ Web Server:"
echo "  - Serves HLS stream via HTTP ($HLS_URL)"
echo "  - Serves annotations file via HTTP ($ANNOTATIONS_URL)"
echo ""

echo "✓ Archive API:"
echo "  - Returned ${ARCHIVE_STREAM_COUNT} archive stream(s) for today ($TODAY)"
echo ""

exit $SUCCESS
