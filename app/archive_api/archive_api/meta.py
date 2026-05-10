import json

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from archive_api import utils
from archive_api.models import ManualAnnotationsRequest

meta_bp = Blueprint("meta", __name__)


@meta_bp.patch("/meta")
def update_meta():
    year = request.args.get("year")
    month = request.args.get("month")
    day = request.args.get("day")
    stream = request.args.get("stream")

    if not all([year, month, day, stream]):
        return jsonify({"error": "Missing required parameters: year, month, day, stream"}), 400

    try:
        body = ManualAnnotationsRequest.model_validate(request.get_json(force=True) or {})
    except ValidationError as e:
        # Convert error objects to JSON-serializable format
        errors = [
            {
                "loc": err.get("loc"),
                "msg": err.get("msg"),
                "type": err.get("type"),
            }
            for err in e.errors()
        ]
        return jsonify({"error": errors}), 422

    stream_path = utils.resolve_stream_path(year, month, day, stream)
    if stream_path is None or not stream_path.is_dir():
        return jsonify({"error": "Recording not found"}), 404

    meta_path = stream_path / "meta.json"
    try:
        with meta_path.open() as f:
            meta = json.load(f)
    except (OSError, json.JSONDecodeError):
        meta = {}

    meta["manual_annotations"] = body.model_dump()["manual_annotations"]

    with meta_path.open("w") as f:
        json.dump(meta, f)

    return jsonify(meta)
