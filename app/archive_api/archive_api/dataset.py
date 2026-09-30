import logging
import queue
import random
import subprocess  # nosec B404
import threading
from pathlib import Path

from archive_api import index_db
from archive_api.models import BirdClass

logger = logging.getLogger(__name__)

DATASET_PATH = Path("/var/www/html/storage/sparrow_cam/dataset")
IMAGES_PATH = DATASET_PATH / "images"
LABELS_PATH = DATASET_PATH / "labels"

_BIRD_CLASS_IDS = {bird_class.value: idx for idx, bird_class in enumerate(BirdClass)}

_queue: queue.Queue = queue.Queue()
_lock = threading.Lock()
_worker_thread: threading.Thread | None = None
_worker_thread_lock = threading.Lock()


def schedule_update(year: str, month: str, day: str, stream_path: Path) -> None:
    """Queue a dataset update for a stream; processed asynchronously by the background worker."""
    _ensure_worker_started()
    _queue.put((year, month, day, stream_path))


def _ensure_worker_started() -> None:
    global _worker_thread
    with _worker_thread_lock:
        if _worker_thread is None:
            _worker_thread = threading.Thread(target=_worker, daemon=True)
            _worker_thread.start()


def _worker() -> None:
    while True:
        year, month, day, stream_path = _queue.get()
        try:
            with _lock:
                _update_stream_dataset(year, month, day, stream_path)
        except Exception:
            logger.exception(f"Failed to process dataset job for {stream_path}")
        finally:
            _queue.task_done()


def _update_stream_dataset(year: str, month: str, day: str, stream_path: Path) -> None:
    IMAGES_PATH.mkdir(parents=True, exist_ok=True)
    LABELS_PATH.mkdir(parents=True, exist_ok=True)

    prefix = f"{year}-{month}-{day}_{stream_path.name}"
    _remove_stream_files(prefix)

    manual_annotations = index_db.get_manual_annotations(f"{year}-{month}-{day}", stream_path.name)
    if manual_annotations is None:
        return

    if manual_annotations == {}:
        _add_negative_sample(stream_path, prefix)
        return

    for segment_name, rois in manual_annotations.items():
        segment_path = stream_path / segment_name
        if not segment_path.is_file():
            continue
        _write_sample(segment_path, f"{prefix}_{segment_path.stem}", rois, positive=True)


def _remove_stream_files(prefix: str) -> None:
    removed = []
    for image_path in IMAGES_PATH.glob(f"{prefix}_*.jpg"):
        image_path.unlink(missing_ok=True)
        removed.append(image_path.name)
    for label_path in LABELS_PATH.glob(f"{prefix}_*.txt"):
        label_path.unlink(missing_ok=True)
        removed.append(label_path.name)
    if removed:
        logger.info(f"Removed {len(removed)} existing dataset file(s) for {prefix}: {removed}")


def _add_negative_sample(stream_path: Path, prefix: str) -> None:
    segments = list(stream_path.glob("*.ts"))
    if not segments:
        return
    segment_path = random.choice(segments)  # nosec B311
    _write_sample(segment_path, f"{prefix}_{segment_path.stem}", [], positive=False)


def _write_sample(segment_path: Path, sample_name: str, rois: list[dict], positive: bool) -> None:
    image_path = IMAGES_PATH / f"{sample_name}.jpg"
    if not _extract_first_frame(segment_path, image_path):
        return
    label_path = LABELS_PATH / f"{sample_name}.txt"
    _write_label(label_path, rois)

    if positive:
        counts: dict[str, int] = {}
        for roi in rois:
            counts[roi["bird_class"]] = counts.get(roi["bird_class"], 0) + 1
        counts_str = ", ".join(f"{bird_class}={count}" for bird_class, count in sorted(counts.items())) or "no birds"
        logger.info(f"Wrote positive sample {image_path.name}/{label_path.name} from {segment_path.name}: {counts_str}")
    else:
        logger.info(f"Wrote negative sample {image_path.name}/{label_path.name} from {segment_path.name}")


def _extract_first_frame(segment_path: Path, dest_path: Path) -> bool:
    # Written to a .tmp path in the destination directory first so the final rename is
    # same-filesystem and atomic, matching the label file write below. The .jpg extension
    # is kept (not appended after) so ffmpeg can infer the output format from it.
    tmp_path = dest_path.with_name(f"{dest_path.stem}.tmp{dest_path.suffix}")
    result = subprocess.run(  # nosec B603 B607
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(segment_path), "-frames:v", "1", "-q:v", "2", str(tmp_path)],
        capture_output=True,
    )
    if result.returncode != 0:
        logger.error(f"ffmpeg failed to extract frame from {segment_path}: {result.stderr.decode(errors='replace')}")
        tmp_path.unlink(missing_ok=True)
        return False
    tmp_path.replace(dest_path)
    return True


def _write_label(label_path: Path, rois: list[dict]) -> None:
    lines = []
    for roi in rois:
        class_id = _BIRD_CLASS_IDS[roi["bird_class"]]
        bbox = roi["bbox"]
        cx = bbox["x"] + bbox["width"] / 2
        cy = bbox["y"] + bbox["height"] / 2
        lines.append(f"{class_id} {cx:.6f} {cy:.6f} {bbox['width']:.6f} {bbox['height']:.6f}")

    content = "\n".join(lines)
    if lines:
        content += "\n"

    tmp_path = label_path.with_name(label_path.name + ".tmp")
    with open(tmp_path, "w") as f:
        f.write(content)
    tmp_path.replace(label_path)
