# Overview
- Source: app/processor/processor/ | Tests: app/processor/tests/
- Purpose: per-segment bird detection, annotation, optional archival

## Model Strategy
Uses a fine-tuned yolo26n model (v0.1.0) trained specifically on bird detection, deployed
as yolo26n_v0.1.0.pt. The fine-tuned model has bird as class ID 0 (not COCO class 14).
Model is created by the Lab package via fine-tuning on a balanced subset of synced field
annotations. For Raspberry Pi deployment, NCNN export of the fine-tuned model can be
generated locally via scripts/export_ncnn.py; deployment path controlled via YOLO_MODEL_PATH
env var.

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

## Detection Metadata Format
Shared contract with archive_api and web:
{"version": 1, "detections": {"segment.ts": [{"class": "bird", "confidence": 0.87, "roi": {...}}]}}

## Bird Type Slugs
Maps fine-tuned model's bird class (ID 0) to "bird" slug. Processor owns authoritative
slug mapping. All written annotation data contains slugs — raw class IDs never leave the
processor.

## Maintenance Window
Between 23:00 (11 PM) and 03:00 (3 AM) local time, the processor skips segment processing
(detection, annotation, archival are all paused). The segments iterator continues consuming
stream segments without processing them, so no backlog accumulates. After 03:00, processing
resumes from the newest available segment. This is environment-gated via MAINTENANCE_WINDOW_ENABLED
and only applies on Raspberry Pi deployment; local dev/docker does not enable this.
