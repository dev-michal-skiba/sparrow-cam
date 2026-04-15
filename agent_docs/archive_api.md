# Overview
- Software: Python package `archive_api`
- Responsibility: Flask HTTP API service for querying archived HLS video segments by date range. Exposes the archive directory structure (nested by year/month/day) as a JSON endpoint with validation for date format, date range limits, and query parameters.

## Package Layout
- Package location: `app/archive_api/`
    - Source code: `app/archive_api/archive_api/`
    - Unit tests: `app/archive_api/tests/`
- Entrypoint for `python -m archive_api`: `app/archive_api/archive_api/__main__.py`

## Modules

### `__main__.py`
Application entry point. Starts the Flask app listening on 0.0.0.0:5001.

### `app.py`
Flask application with two archive API endpoints and bird filtering support.

Helper functions:
- `get_stream_birds()` — reads `meta.json` from a stream directory and extracts sorted list of unique detected bird species (classes) from all detections
- `parse_bird_filter()` — parses comma-separated bird species string from query parameter
- `stream_matches_filter()` — determines if a stream contains any of the requested bird species (or all streams if filter is empty)

#### GET `/` — List archive by date range
- Lists archived HLS streams filtered by date range (served at `/archive/api` by nginx with path prefix stripping)
- Date validation — validates required query parameters `from` and `to` with YYYY-MM-DD format
- Date range validation — enforces maximum 31-day query window (inclusive) and validates `from` date is not after `to` date
- Archive structure discovery — walks the nested year/month/day directory structure, enumerates stream folders at each day directory, returns nested JSON object mapping year → month → day → stream names
- Returns empty object if no streams exist in the queried range
- Stream names are sorted alphabetically within each day
- Stream metadata — includes `birds` array with species detected in each stream
- Optional bird filtering — supports `birds` query parameter (comma-separated species names) to filter results to only streams containing those species

#### GET `/adjacent` — Navigate adjacent recordings
- Accepts required query parameters: year, month, day, stream
- Enumerates all recordings in the archive in chronological and alphabetical order (year/month/day/stream)
- Finds the current recording by matching all four parameters
- Returns JSON object with `previous` and `next` fields, each containing year/month/day/stream fields or null if no adjacent recording exists
- Returns 400 if any required parameter is missing
- Returns 404 if the specified recording is not found
- Optional bird filtering — supports `birds` query parameter to filter the list of adjacent recordings to only those containing specified species

## Unit Tests

```
make -C local archive-api-test
```
Pass extra pytest flags via `ARGS`:
```
make -C local archive-api-test ARGS="-vv"
```

Test coverage organized into two test classes:
- `TestDateValidation` — validates date parsing, format checking, range limits, and boundary conditions
- `TestArchiveListing` — validates directory traversal, stream enumeration, filtering by date range, and response structure

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
