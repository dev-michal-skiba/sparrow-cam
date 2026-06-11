- Source: app/archive_api/archive_api/ | Tests: app/archive_api/tests/

## Purpose
HTTP API for querying archived streams by date range and managing manual annotations.

## Domain Rules

- 31-day maximum query window — prevents unbounded directory traversal.
- Adjacent endpoint does not filter the middle stream — current recording always
  navigable regardless of active filter; only previous/next are filtered.
- Annotation filters are mutually exclusive — `exclude_annotated` and
  `include_false_positives` cannot both be set; returns 400.
- PATCH /meta preserves detections — only `manual_annotations` is replaced;
  existing detection data is never touched.
- Bird enumeration prefers manual annotations — when querying birds from a
  stream, `manual_annotations` takes precedence over `detections` if present.
