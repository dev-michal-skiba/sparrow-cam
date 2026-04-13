# Overview
- Software: Python package `processor`
- Responsibility: Monitors HLS video segments from a live camera stream, detects birds using YOLOv8, annotates detection results to a JSON file, and optionally archives segments when birds are detected. Runs continuously as a background service on a Raspberry Pi.

## Package Layout
- Package location: `app/processor/`
    - Source code: `app/processor/processor/`
    - Unit tests: `app/processor/tests/`
- Entrypoint for `python -m processor`: `app/processor/processor/__main__.py`

## Modules

### `__main__.py`
- Application entry point
- Sets up logging and starts the main processing loop

### `hls_segment_processor.py`
- Central orchestrator
- Main event loop that consumes new HLS segments
- Per-segment bird detection — samples evenly distributed frames, crops each to configured detection regions, collects detection details (class name, confidence, region of interest)
- Records detection metadata via StreamArchiver after each segment
- Delegates archive scheduling to StreamArchiver with detection results
- Annotation pruning after each segment

### `hls_watchtower.py`
- HLS stream monitor
- Watches playlist file and yields new segments as they appear
- Playlist polling with exponential backoff
- Segment deduplication

### `bird_detector.py`
- Fine-tuned YOLOv8 model wrapper for bird detection
- Loads and fuses a custom model trained to detect specific bird species (Great Tit, Pigeon)
- Methods to detect bird presence in frames and retrieve bounding boxes with associated class IDs and confidence scores
- Resolves class IDs to human-readable species names via the YOLO model's names dictionary
- Defaults to bundled fine-tuned model but supports custom model paths

### `bird_annotator.py`
- Detection result persistence
- Manages JSON sidecar file mapping segments to detection results
- Recording new annotations and pruning stale entries

### `stream_archiver.py`
- HLS segment archival, extension, and archive scheduling orchestration
- Owns all archive configuration and scheduling logic with delayed trigger and overlap prevention
- Archive scheduling driven per-segment by HLSSegmentProcessor calling on_segment()
  - When bird detected in overlap zone (region near previous archive), extends the previous archive with additional segments instead of creating a new archive
- Records per-segment detection metadata (class, confidence, region of interest) in memory with automatic pruning of stale entries when segments expire from the live playlist
- Writes detection metadata to `meta.json` alongside archive files after archival or extension
  - When extending an existing archive, preserves detections from the existing `meta.json` file and merges them with current in-memory detections, ensuring data for segments pruned from the live playlist is not lost
  - Includes only segments with at least one detection in the merged result
- Creates new timestamped archives of current stream segments and extends existing archives with additional segments
- Validates inputs, filters playlist to configurable segment window
- Cleans up excess files
- Runnable as standalone CLI for manual archiving
- Returns archive directory path on successful creation

### `types.py`
- Custom data structures used across the package
- Defines the detection box structure as a named tuple with box coordinates, class ID, and confidence score

### `constants.py`
- Shared path constants and configuration values

### `utils.py`
- Utility functions for loading detection preset configuration

## Archive Metadata Format

When archives are created or extended, a `meta.json` file is written alongside the archive files containing detection metadata for each segment. The file structure is:

```json
{
  "version": 1,
  "detections": {
    "segment-name.ts": [
      {"class": "Pigeon", "confidence": 0.8701, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}}
    ]
  }
}
```

The `detections` dict includes only segments with at least one detection. The file is always created even if no detections occurred in any segment.

## Related Files
- Processor Dockerfile: `local/Dockerfile`
- Processor Docker Compose: `local/docker-compose.yml`

## Unit Tests

```
make -C local test
```
Pass extra pytest flags via `ARGS`:
```
make -C local test ARGS="-vv"
```

## Formatting

Runs `black` and `ruff check --fix`.

```
make -C local format
```

## Linting & Type Checking

Runs `ruff check`, `pyright`, and `bandit -r processor` (security linter).

```
make -C local check
```
