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
Flask application with the archive API endpoint:
- Defines `/` GET endpoint that lists archived HLS streams filtered by date range (served at `/archive/api` by nginx with path prefix stripping)
- Date validation — validates required query parameters `from` and `to` with YYYY-MM-DD format
- Date range validation — enforces maximum 31-day query window (inclusive) and validates `from` date is not after `to` date
- Archive structure discovery — walks the nested year/month/day directory structure, enumerates stream folders at each day directory, returns nested JSON object mapping year → month → day → stream names
- Returns empty object if no streams exist in the queried range
- Stream names are sorted alphabetically within each day
- Stream metadata (nested under stream name) is currently empty

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

## E2E Tests

Archive API is covered by the shared e2e test suite. The e2e tests verify:
- Archive API container is running
- Archive API is accessible via nginx at `http://localhost:8080/archive/api`
- Archive API returns valid JSON for a date range query
- Archive API returns archive data for archives created during the e2e test run

Run e2e tests (includes archive API):

```
make -C local e2e
```

E2E tests require up to 10 minutes to complete

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
