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
- Per-segment bird detection — samples evenly distributed frames, crops each to configured detection regions
- Archive scheduling with delayed trigger and overlap prevention between consecutive archives
- Annotation pruning after each segment

### `hls_watchtower.py`
- HLS stream monitor
- Watches playlist file and yields new segments as they appear
- Playlist polling with exponential backoff
- Segment deduplication

### `bird_detector.py`
- Fine-tuned YOLOv8 model wrapper for bird detection
- Loads and fuses a custom model trained to detect specific bird species (Great Tit, Pigeon)
- Methods to detect bird presence in frames and retrieve bounding boxes with associated class IDs
- Defaults to bundled fine-tuned model but supports custom model paths

### `bird_annotator.py`
- Detection result persistence
- Manages JSON sidecar file mapping segments to detection results
- Recording new annotations and pruning stale entries

### `stream_archiver.py`
- HLS segment archival
- Copies current stream into timestamped archive directories
- Validates inputs, filters playlist to configurable segment window
- Cleans up excess files
- Runnable as standalone CLI for manual archiving

### `types.py`
- Custom data structures used across the package
- Defines the detection box structure as a named tuple with box coordinates and class ID

### `constants.py`
- Shared path constants and configuration values

### `utils.py`
- Utility functions for loading detection preset configuration

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

## E2E Tests

```
make -C local e2e
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
