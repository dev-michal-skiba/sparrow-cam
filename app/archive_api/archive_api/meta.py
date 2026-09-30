import json

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from archive_api import dataset, index_db, utils
from archive_api.models import ManualAnnotationsRequest

meta_bp = Blueprint("meta", __name__)


@meta_bp.get("/meta")
def get_meta():
    year = request.args.get("year")
    month = request.args.get("month")
    day = request.args.get("day")
    stream = request.args.get("stream")

    if not all([year, month, day, stream]):
        return jsonify({"error": "Missing required parameters: year, month, day, stream"}), 400

    _, err = utils.parse_date(f"{year}-{month}-{day}", "year/month/day")
    if err:
        return jsonify(err), 400

    conn = index_db.get_connection()
    try:
        meta = index_db.get_meta(conn, f"{year}-{month}-{day}", stream)
    finally:
        conn.close()
    if meta is None:
        return jsonify({"error": "Recording not found"}), 404

    return jsonify(meta)


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

    manual_annotations = body.model_dump()["manual_annotations"]
    date = f"{year}-{month}-{day}"
    meta_path = stream_path / "meta.json"

    conn = index_db.get_connection()
    try:
        with conn:
            cursor = conn.execute(
                "UPDATE recordings SET manual_annotations = ?, birds = ? WHERE date = ? AND stream = ?",
                (
                    json.dumps(manual_annotations),
                    json.dumps(index_db.birds_from_annotations(manual_annotations)),
                    date,
                    stream,
                ),
            )
            if cursor.rowcount == 0:
                return jsonify({"error": "Recording not found"}), 404

            try:
                with meta_path.open() as f:
                    meta = json.load(f)
            except (OSError, json.JSONDecodeError):
                meta = {}
            meta["manual_annotations"] = manual_annotations
            with meta_path.open("w") as f:
                json.dump(meta, f)
    finally:
        conn.close()

    dataset.schedule_update(year, month, day, stream_path)

    return jsonify(meta)
