- Source: app/archive_api/archive_api/ | Tests: app/archive_api/tests/

## Purpose
HTTP API for querying archived streams by date range and managing manual annotations.

## Data Storage
Index.db is an SQLite database that stores the source of truth for all queries and
filtering. Each recording is a row with: date (YYYY-MM-DD), stream (name), detections
(JSON), manual_annotations (JSON or NULL), and birds (JSON array of unique bird slugs
derived from manual_annotations when set; otherwise derived from detections).

The processor writes detections and derives birds on every stream update; the API
writes manual_annotations and derives birds when annotations change. All data flows
through the database.

## Domain Rules

- 31-day maximum query window — prevents unbounded query cost.
- Birds column is the authoritative source for bird enumeration and filtering. It is
  derived from manual_annotations if present; otherwise from detections.
- Adjacent endpoint does not filter the middle stream — current recording always
  navigable regardless of active filter; only previous/next are filtered.
- Annotation filters are mutually exclusive — `exclude_annotated` and
  `exclude_false_positives` cannot both be set; returns 400.
- PATCH /meta preserves detections — only `manual_annotations` and `birds` are
  updated in a single transaction; existing detection data is never touched.
- GET /meta returns detections plus manual_annotations (if set); PATCH /meta updates
  both in the database.

## Bird Type Slugs
Bird types are slugs throughout. Manual annotations enforce the valid slug set via
an enum; auto-detection slugs are trusted as correct since the processor guarantees
them. The birds column (derived from manual_annotations or detections) is queried by
bird filters; GET / and GET /adjacent filter only on birds that appear in the column.

## Dataset Generation
PATCH /meta triggers asynchronous dataset building for training YOLO on manual
annotations, but returns immediately — dataset processing happens in the background.
An update job is enqueued once per PATCH; jobs execute serially (one at a time).

Dataset building reads manual_annotations from the database before
processing, ensuring it operates on the validated annotations written in the PATCH
transaction.

Dataset building workflow:
- Purges prior dataset files for that stream/date via prefix matching, logs removals.
- If manual_annotations is empty ({}), treats as negative sample: picks a random .ts
  segment, extracts its first frame via ffmpeg, writes with empty label file.
- If annotations present, treats as positive samples: for each annotated segment,
  extracts first frame and writes YOLO-format label (class_id cx cy w h with
  normalized center-coordinates; class_id is the bird's index in BirdClass enum).
- All image/label writes are atomic (temp file + rename).
- On success, logs written samples with per-bird-class annotation counts.
