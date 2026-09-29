import json
import logging
from pathlib import Path

from processor.constants import LOG_FORMAT
from processor.index_db import get_connection

ARCHIVE_PATH = Path("/var/www/html/storage/sparrow_cam/archive")

logger = logging.getLogger(__name__)


def get_birds(meta: dict) -> list[str]:
    """Derive bird classes from meta, mirroring archive_api's precedence rule.

    manual_annotations take precedence over detections when present.
    """
    birds: set[str] = set()
    manual_annotations = meta.get("manual_annotations")
    if manual_annotations is not None:
        for annotations in manual_annotations.values():
            for ann in annotations:
                if "bird_class" in ann:
                    birds.add(ann["bird_class"])
    else:
        for detections in meta.get("detections", {}).values():
            for det in detections:
                if "class" in det:
                    birds.add(det["class"])
    return sorted(birds)


def backfill() -> None:
    """Insert a recordings row for every meta.json that doesn't already have one.

    Existing rows (e.g. from the processor's dual-write, or a previous run of this
    script) are left untouched, so the script is safe to rerun at any time.
    """
    inserted = 0
    skipped_existing = 0
    skipped_corrupt = 0

    conn = get_connection()
    try:
        for meta_path in sorted(ARCHIVE_PATH.rglob("meta.json")):
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                year, month, day, stream = meta_path.parent.relative_to(ARCHIVE_PATH).parts
                detections = meta.get("detections", {})
                manual_annotations = meta.get("manual_annotations")
                birds = get_birds(meta)
            except (OSError, json.JSONDecodeError, ValueError, AttributeError) as exc:
                logger.warning(f"Skipping corrupt meta.json at {meta_path}: {exc}")
                skipped_corrupt += 1
                continue

            with conn:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO recordings (date, stream, detections, manual_annotations, birds)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        f"{year}-{month}-{day}",
                        stream,
                        json.dumps(detections),
                        json.dumps(manual_annotations) if manual_annotations is not None else None,
                        json.dumps(birds),
                    ),
                )
            if cursor.rowcount:
                inserted += 1
            else:
                skipped_existing += 1
    finally:
        conn.close()

    logger.info(
        f"Inserted: {inserted}, skipped (already present): {skipped_existing}, skipped (corrupt): {skipped_corrupt}"
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[logging.StreamHandler()],
    )
    backfill()
