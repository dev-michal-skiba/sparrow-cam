# Overview
- Software: Python package `archive_api`
- Responsibility: Flask HTTP API service for querying archived HLS video segments by date range, and managing manual annotations. Exposes the archive directory structure (nested by year/month/day) as JSON endpoints with validation for date format, date range limits, and query parameters.

## Package Layout
- Package location: `app/archive_api/`
    - Source code: `app/archive_api/archive_api/`
    - Unit tests: `app/archive_api/tests/`
- Entrypoint for `python -m archive_api`: `app/archive_api/archive_api/__main__.py`

## Modules

### `__main__.py`
Application entry point. Starts the Flask app listening on 0.0.0.0:5001.

### `app.py`
Initializes the Flask application and registers two blueprints: archive blueprint for archive querying endpoints and meta blueprint for metadata management endpoints.

### `archive.py`
Flask blueprint with archive querying endpoints (GET `/` and GET `/adjacent`). Handles listing archived streams by date range and navigation between adjacent recordings with optional bird species filtering.

### `meta.py`
Flask blueprint with metadata management endpoints. Contains the PATCH `/meta` endpoint for updating manual annotations in stream metadata files.

### `models.py`
Pydantic data models for request validation:
- `ManualAnnotationsRequest` — validates request body for manual annotation updates
- `MetaFile` — schema for the meta.json file structure with optional manual_annotations field

### `utils.py`
Helper functions and constants for shared functionality:
- `ARCHIVE_PATH`, `DATE_PATTERN`, `MAX_RANGE_DAYS` — constants for archive configuration
- `parse_date()` — validates and parses date strings in YYYY-MM-DD format
- `get_stream_birds()` — reads meta.json from a stream directory and extracts sorted list of unique detected bird species
- `parse_bird_filter()` — parses comma-separated bird species string from query parameter
- `stream_matches_filter()` — determines if a stream contains requested bird species
- `parse_bool_filter()` — parses "true"/"1" query parameter values to boolean
- `parse_annotations_filter()` — parses and validates annotation filter parameters, ensuring both cannot be set simultaneously
- `get_stream_manual_annotations()` — reads manual_annotations from meta.json
- `stream_matches_annotations_filter()` — applies annotation filters (false positives inclusion, annotated exclusion) to a stream

## Endpoints

### GET `/` — List archive by date range
- Lists archived HLS streams filtered by date range (served at `/archive/api` by nginx with path prefix stripping)
- Date validation — validates required query parameters `from` and `to` with YYYY-MM-DD format
- Date range validation — enforces maximum 31-day query window (inclusive) and validates `from` date is not after `to` date
- Archive structure discovery — walks the nested year/month/day directory structure, enumerates stream folders at each day directory, returns nested JSON object mapping year → month → day → stream names
- Returns empty object if no streams exist in the queried range
- Stream names are sorted alphabetically within each day
- Stream metadata — includes `birds` array with species detected in each stream
- Optional bird filtering — supports `birds` query parameter (comma-separated species names) to filter results to only streams containing those species
- Annotation filtering — supports optional `include_false_positives` and `exclude_annotated` query parameters (mutually exclusive) to filter by manual annotation status; returns 400 error if both are set simultaneously

### GET `/adjacent` — Navigate adjacent recordings
- Accepts required query parameters: year, month, day, stream
- Enumerates all recordings in the archive in chronological and alphabetical order (year/month/day/stream)
- Finds the current recording by matching all four parameters
- Returns JSON object with `previous` and `next` fields, each containing year/month/day/stream fields or null if no adjacent recording exists
- Returns 400 if any required parameter is missing
- Returns 404 if the specified recording is not found
- Optional bird filtering — supports `birds` query parameter to filter the list of adjacent recordings to only those containing specified species
- Annotation filtering — supports optional `include_false_positives` and `exclude_annotated` query parameters (mutually exclusive) to filter by manual annotation status; returns 400 error if both are set simultaneously

### PATCH `/meta` — Update manual annotations
- Updates manual annotations for a specific stream recording
- Required query parameters: year, month, day, stream (all must be present)
- Request body: JSON object with `manual_annotations` field containing annotation data, validated with pydantic
- Returns 400 if required query parameters are missing
- Returns 404 if the specified stream recording is not found
- Returns 422 if request body validation fails (invalid pydantic model)
- Returns 200 with the updated meta.json content on success
- Updates the meta.json file in the stream directory, preserving existing detections and replacing any existing manual_annotations

## Unit Tests

```
make -C local archive-api-test
```
Pass extra pytest flags via `ARGS`:
```
make -C local archive-api-test ARGS="-vv"
```

Test files:
- `test_archive.py` — tests for archive querying endpoints (GET `/` and GET `/adjacent`), including date validation, directory traversal, stream enumeration, and bird filtering
- `test_meta.py` — tests for the PATCH `/meta` endpoint including parameter validation, error handling, and manual annotation updates
- `test_utils.py` — unit tests for utility functions: date parsing, bird filtering, and stream matching logic

## Formatting

Runs `black` and `ruff check --fix`.

```
make -C local archive-api-format
```

## Linting & Type Checking

Runs `ruff check`, `pyright`, and `bandit -r archive_api` (security linter).

```
make -C local archive-api-check
```
