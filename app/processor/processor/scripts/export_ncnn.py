import argparse
import os
from pathlib import Path

from ultralytics import YOLO

MODELS_DIR = Path(__file__).parent.parent / "models"


def main() -> None:
    parser = argparse.ArgumentParser(description="Export YOLO .pt model to NCNN format")
    parser.add_argument("model", help="Model filename in models/ directory (e.g. yolo26n.pt)")
    args = parser.parse_args()

    # chdir so ultralytics downloads the model here and saves the NCNN export here
    os.chdir(MODELS_DIR)

    model_path = MODELS_DIR / args.model
    model = YOLO(str(model_path) if model_path.exists() else args.model)
    model.export(format="ncnn")


if __name__ == "__main__":
    main()
