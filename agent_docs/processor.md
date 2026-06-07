# Overview
- Source: app/processor/processor/ | Tests: app/processor/tests/
- Purpose: per-segment bird detection, annotation, optional archival

## Per-Class Thresholds
The minimum across all class thresholds is used for the initial YOLO call, then
results are filtered per-class afterward. This prevents missed detections when
one species has a high threshold while another has a low one.

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
{"version": 1, "detections": {"segment.ts": [{"class": "...", "confidence": 0.87, "roi": {...}}]}}
