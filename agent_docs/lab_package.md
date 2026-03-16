# Overview
- Software: Python package `lab`
- Responsibility: Desktop GUI tool for managing the bird detection dataset.

## Package Layout
- Package location: `app/lab/`
    - Source code: `app/lab/lab/`
    - Unit tests: `app/lab/tests/`
- Entrypoint for `python -m lab`: `app/lab/lab/__main__.py`

## Modules

### `__main__.py`
Application entry point. Creates storage directories (`archive/`, `images/`), instantiates `LabGUI`, and starts the tkinter main loop.

### `gui.py`
Tkinter-based GUI (`LabGUI` class). Provides:
- Sync workflow
    - Shows a modal dialog to optionally specify a date range (from/to dates, defaults to today) to filter which remote recordings to sync
    - Fetches the list of missing folders from the remote server in a background thread
    - Once the list is ready, displays a confirmation step showing the recording count and timeframe, asking the user to proceed or cancel
    - Upon confirmation, downloads new HLS streams from the Pi via SFTP
    - Converts HLS stream to PNGs
    - Cleans up HLS files locally
    - File browser for navigating synced recording images
    - Recording removal dialog — delete recordings locally or both locally and remotely
- Detection
    - Pick between base YOLOv8n and fine-tuned models for detection
    - Set detection region, yolo detection parameters
        - Export/import it to/from file
    - Test bird detection on different images
- Annotation
    - Manually annotate birds on images and update local dataset
    - Dataset statistics display (per-class train/val counts) always visible
- Fine-tune dialog — collects version, description, and optional crop preset, then runs training in a background thread with a Cancel button to stop training and clean up partial output
- FPS tracking — reads actual FPS from `stream_info.json` during recording playback, with fallback to calculated frames-per-segment for older streams

### `annotations.py`
YOLO dataset management. Handles:
- Saving/loading/removing bounding-box annotations in YOLO txt format
- Automatic train/val split with ~80/20 ratio (per-class balancing for positives, separate balancing for negatives)
- Dataset structure creation and `dataset.yaml` generation
- Conversion between pixel coordinates and normalized YOLO format
- Dataset statistics (total/positive/negative counts per split, per-class file counts and per-class bounding-box annotation counts, total annotation count across all classes)

### `converter.py`
- Converts archived `.ts` HLS video segments into PNG frames using OpenCV
- Walks the nested `year/month/day/folder` archive structure, identifies unconverted playlists, and extracts every frame from each `.ts` file
- Reads actual FPS from the video stream during conversion and saves it to `stream_info.json` in the output folder

### `sync.py`
SFTP-based sync manager that downloads HLS archive folders from the production Raspberry Pi. Features:
- SSH connection via Ed25519/RSA key from mounted secrets
- Remote archive folder discovery (nested date structure) with optional date range filtering (from date / to date inclusive)
- Per-file download with automatic retry and reconnection (up to 15 attempts)
- Recording removal — both remote+local and local-only variants
- HLS file cleanup (removes `.ts`/`.m3u8` while keeping the folder as a sync marker)

### `fine_tune.py`
YOLOv8 fine-tuning pipeline:
- Validates semantic version format (`v<major>.<minor>.<patch>`)
- Lists available fine-tuned models from `FINE_TUNED_MODELS_DIR`
- Optionally crops the dataset to a preset detection region before training with intelligent frame filtering:
    - Positive frames (frames with annotations) are included only if ALL annotation boxes are fully within the detection region; frames with any box extending outside are discarded
    - Negative frames (frames without annotations) are randomly subsampled to preserve the original positive-to-negative ratio
- Runs `YOLO.train()` (100 epochs, batch 16, imgsz 480 by default)
- Saves `model.pt` + `meta.json` (version, description, classes, metrics) per version
- Supports cancellation: training can be stopped via a cancellation signal, which raises `TrainingCancelledError` and allows cleanup of partial output

### `constants.py`
Shared path constants and regex patterns:
- Storage directories: `ARCHIVE_DIR`, `IMAGES_DIR`, `PRESETS_DIR`, `DATASET_DIR`, `FINE_TUNED_MODELS_DIR` (all under `/.storage/`)
- Secrets: `SSH_KEY_PATH`, `CONFIG_PATH` (mounted at `/secrets/`)
- `REMOTE_ARCHIVE_PATH` — remote server archive location
- `ARCHIVE_FOLDER_PATTERN` — regex for `[prefix_]ISO-timestamp_uuid` folder names
- `IMAGE_FILENAME_PATTERN` — regex for `{prefix}-{segment}-{frame}.png`

### `utils.py`
Business logic utilities for bird detection and image processing:
- Path validation (ensures files are inside storage boundary)
- Frame loading and annotation rendering (draws detection boxes on images)
- `get_annotated_image_bytes()` — runs `BirdDetector` on an image (optionally cropped to regions), annotates detected boxes, returns base64-encoded PNG

### `exception.py`
Defines `UserFacingError` — an exception with `title`, `message`, and `severity` ("error" or "info") for displaying popup dialogs via the `@handle_user_error` decorator in `gui.py`.

## Related Files
- Lab Dockerfile: `local/Dockerfile.lab`
- Lab Docker Compose: `local/docker-compose.lab.yml`

## Unit Tests

```
make -C local lab-test
```
Pass extra pytest flags via `ARGS`:
```
make -C local lab-test ARGS="-vv"
```

- do not implement tests for `gui.py`
    - it's skipped from coverage

## E2E Tests

Lab package DOES NOT implement E2E tests

## Formatting

Runs `black` and `ruff check --fix`.

```
make -C local make lab-format
```

## Linting & Type Checking
```
Runs `ruff check`, `pyright`, and `bandit -r lab` (security linter).

```
make -C local make lab-check
