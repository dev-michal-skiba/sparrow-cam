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

## Detection Metadata Format
Shared contract with archive_api and web:
{"version": 1, "detections": {"segment.ts": [{"class": "bird", "confidence": 0.87, "roi": {...}}]}}

## Bird Type Slugs
Currently maps COCO bird class to "bird" slug. Processor owns authoritative slug mapping.
All written annotation data contains slugs — raw class IDs never leave the processor.
