"""Model evaluation: COCO-style metrics for fine-tuned YOLOv8 models."""

from __future__ import annotations

import json
import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path

from lab.constants import FINE_TUNED_MODELS_DIR

EVALUATION_DIR_NAME = "evaluation"


def get_models_without_evaluation() -> list[dict]:
    """
    Return fine-tuned models that have no evaluation yet.

    Each dict contains version, model_path, description, created_at.
    Sorted by created_at descending (newest first).
    """
    models: list[dict] = []

    if not FINE_TUNED_MODELS_DIR.exists():
        return models

    for version_dir in FINE_TUNED_MODELS_DIR.iterdir():
        if not version_dir.is_dir():
            continue

        meta_path = version_dir / "meta.json"
        model_path = version_dir / "model.pt"
        eval_dir = version_dir / EVALUATION_DIR_NAME

        if not meta_path.exists() or not model_path.exists():
            continue

        # Skip models that already have evaluation
        if eval_dir.exists() and (eval_dir / "results.json").exists():
            continue

        try:
            with open(meta_path) as f:
                meta = json.load(f)

            models.append(
                {
                    "version": version_dir.name,
                    "model_path": str(model_path),
                    "description": meta.get("description", ""),
                    "created_at": meta.get("created_at", ""),
                }
            )
        except (json.JSONDecodeError, OSError):
            continue

    models.sort(key=lambda m: m["created_at"], reverse=True)
    return models


class EvaluationCancelledError(Exception):
    """Raised when evaluation is cancelled via a cancel event."""


def run_evaluation(
    version: str,
    cancel_event: threading.Event | None = None,
) -> Path:
    """
    Run COCO-style evaluation on a fine-tuned model's validation set.

    Loads the model and its training dataset, runs model.val() to compute
    COCO metrics, then saves all results and plots to
    FINE_TUNED_MODELS_DIR/{version}/evaluation/.

    Returns the evaluation output directory path.
    """
    from ultralytics import YOLO  # imported here to avoid slow startup at module load

    version_dir = FINE_TUNED_MODELS_DIR / version
    model_path = version_dir / "model.pt"
    meta_path = version_dir / "meta.json"
    dataset_dir = version_dir / "dataset"
    dataset_yaml = dataset_dir / "dataset.yaml"
    eval_dir = version_dir / EVALUATION_DIR_NAME

    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    if not meta_path.exists():
        raise FileNotFoundError(f"Meta file not found: {meta_path}")
    if not dataset_yaml.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_yaml}")

    if cancel_event is not None and cancel_event.is_set():
        raise EvaluationCancelledError("Evaluation cancelled.")

    eval_dir.mkdir(parents=True, exist_ok=True)

    # Use a temp runs dir inside eval_dir for ultralytics artefacts
    runs_dir = eval_dir / "runs"
    runs_dir.mkdir(exist_ok=True)

    model = YOLO(str(model_path))

    if cancel_event is not None and cancel_event.is_set():
        raise EvaluationCancelledError("Evaluation cancelled.")

    results = model.val(
        data=str(dataset_yaml),
        split="val",
        project=str(runs_dir),
        name="eval",
        exist_ok=True,
        plots=True,
    )

    if cancel_event is not None and cancel_event.is_set():
        raise EvaluationCancelledError("Evaluation cancelled.")

    # Extract comprehensive metrics
    with open(meta_path) as f:
        meta = json.load(f)
    class_names = meta.get("classes", {})

    metrics: dict = {}
    class_metrics: list[dict] = []

    if results is not None:
        try:
            rd = results.results_dict

            metrics = {
                "mAP50": float(rd.get("metrics/mAP50(B)", 0)),
                "mAP50-95": float(rd.get("metrics/mAP50-95(B)", 0)),
                "precision": float(rd.get("metrics/precision(B)", 0)),
                "recall": float(rd.get("metrics/recall(B)", 0)),
            }

            # Per-class metrics
            try:
                ap50_per_class = results.box.ap50
                ap_per_class = results.box.ap
                p_per_class = results.box.p
                r_per_class = results.box.r

                for i, class_id in enumerate(sorted(class_names.keys(), key=int)):
                    if i < len(ap50_per_class):
                        class_metrics.append(
                            {
                                "class_id": int(class_id),
                                "class_name": class_names[class_id],
                                "AP50": float(ap50_per_class[i]),
                                "AP50-95": float(ap_per_class[i]),
                                "precision": float(p_per_class[i]),
                                "recall": float(r_per_class[i]),
                            }
                        )
            except (AttributeError, IndexError, TypeError):
                pass

        except (AttributeError, TypeError):
            pass

    # Copy plots from ultralytics output to evaluation dir
    eval_run_dir = runs_dir / "eval"
    if eval_run_dir.exists():
        for plot_file in eval_run_dir.glob("*.png"):
            shutil.copy2(plot_file, eval_dir / plot_file.name)
        for plot_file in eval_run_dir.glob("*.csv"):
            shutil.copy2(plot_file, eval_dir / plot_file.name)

    # Clean up runs dir
    shutil.rmtree(runs_dir, ignore_errors=True)

    # Build and save results
    eval_results = {
        "version": version,
        "evaluated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dataset": str(dataset_yaml),
        "metrics": metrics,
        "class_metrics": class_metrics,
    }

    (eval_dir / "results.json").write_text(json.dumps(eval_results, indent=2))

    return eval_dir
