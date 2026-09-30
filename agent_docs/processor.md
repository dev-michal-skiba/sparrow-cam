# Overview
- Source: app/processor/processor/ | Tests: app/processor/tests/
- Purpose: per-segment bird detection, annotation, optional archival

## Model Strategy
Using yolo26n model with COCO class 14 for bird. Detects generic birds across full frame.
For Raspberry Pi, NCNN export can be built locally via scripts/export_ncnn.py;
deployment via YOLO_MODEL_PATH env var.

## Detection Parameters
Detection uses class confidence threshold from preset JSON. Per-class thresholds remain
supported for future species-specific models. Image size standardized to 640x640.

## Archive Race Condition Prevention
When archiving, the live playlist is parsed and filtered before any segment files
are copied. This ordering prevents a race condition where the HLS stream service
could delete segments from the live stream after we identify them but before we copy
them to the archive directory. Always filter the playlist data from the live stream
first, then copy only the segments in that filtered data.

## Archive Extension
When a bird is detected in the overlap zone near the previous archive's window,
that archive is extended rather than a new one created. This preserves continuity
of a single visit across segment boundaries.

## Disabling Archiving
Archiving can be disabled via a flag file with no service restart needed.
Detection and live annotation continue normally while the flag file is present.

## Extend Merges meta.json
When extending an existing archive, the existing meta.json is read and merged
with in-memory detections. This ensures data for segments already pruned from
the live playlist is not lost.

## Index Database
All archives are persisted to SQLite (index.db) keyed on (date, stream). The recordings table
is upserted after each archive or extension, with date in YYYY-MM-DD format and stream as the
archive directory name. On conflict, the detections column is always updated, while birds and
manual_annotations are preserved via conditional logic: birds is updated only when
manual_annotations is null (archive_api owns the birds column when manual annotations exist);
manual_annotations themselves are never overwritten. The database mirrors detections from
meta.json—both are written from the same merged dict in a single transaction, so they remain
in sync. The birds column is derived from detections via extracting and sorting unique bird
class slugs.

## Detection Metadata Format
Shared contract with archive_api and web:
{"version": 1, "detections": {"segment.ts": [{"class": "bird", "confidence": 0.87, "roi": {...}}]}}

## Bird Type Slugs
Currently maps COCO bird class to "bird" slug. Processor owns authoritative slug mapping.
All written annotation data contains slugs — raw class IDs never leave the processor.

## Maintenance Window
Between 23:00 (11 PM) and 03:00 (3 AM) local time, the processor skips segment processing
(detection, annotation, archival are all paused). The segments iterator continues consuming
stream segments without processing them, so no backlog accumulates. After 03:00, processing
resumes from the newest available segment. This is environment-gated via MAINTENANCE_WINDOW_ENABLED
and only applies on Raspberry Pi deployment; local dev/docker does not enable this.
