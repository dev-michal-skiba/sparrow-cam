- Source: app/archive_api/archive_api/ | Tests: app/archive_api/tests/

## Purpose
HTTP API for querying archived streams by date range and managing manual annotations.

## Domain Rules

- 31-day maximum query window — prevents unbounded directory traversal.
- Adjacent endpoint does not filter the middle stream — current recording always
  navigable regardless of active filter; only previous/next are filtered.
- Annotation filters are mutually exclusive — `exclude_annotated` and
  `exclude_false_positives` cannot both be set; returns 400.
- PATCH /meta preserves detections — only `manual_annotations` is replaced;
  existing detection data is never touched.
- Bird enumeration prefers manual annotations — when querying birds from a
  stream, `manual_annotations` takes precedence over `detections` if present.

## Bird Type Slugs
Bird types are slugs throughout. Manual annotations enforce the valid slug set via
an enum; auto-detection slugs are trusted as correct since the processor guarantees
them.

## Dataset Generation
PATCH /meta triggers asynchronous dataset building for training YOLO on manual
annotations, but returns immediately — dataset processing happens in the background.
An update job is enqueued once per PATCH; jobs execute serially (one at a time).

Dataset building workflow:
- Purges prior dataset files for that stream/date via prefix matching, logs removals.
- If manual_annotations is empty ({}), treats as negative sample: picks a random .ts
  segment, extracts its first frame via ffmpeg, writes with empty label file.
- If annotations present, treats as positive samples: for each annotated segment,
  extracts first frame and writes YOLO-format label (class_id cx cy w h with
  normalized center-coordinates; class_id is the bird's index in BirdClass enum).
- All image/label writes are atomic (temp file + rename).
- On success, logs written samples with per-bird-class annotation counts.
