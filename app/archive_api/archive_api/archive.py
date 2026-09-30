import json

from flask import Blueprint, jsonify, request

from archive_api import index_db, utils

archive_bp = Blueprint("archive", __name__)


@archive_bp.get("/adjacent")
def get_adjacent():
    year = request.args.get("year")
    month = request.args.get("month")
    day = request.args.get("day")
    stream = request.args.get("stream")

    if not all([year, month, day, stream]):
        return jsonify({"error": "Missing required parameters: year, month, day, stream"}), 400

    _, err = utils.parse_date(f"{year}-{month}-{day}", "year/month/day")
    if err:
        return jsonify(err), 400

    if not utils.is_safe_path_component(stream):
        return jsonify({"error": "Recording not found"}), 404

    bird_filter = utils.parse_bird_filter(request.args.get("birds"))
    exclude_false_positives, exclude_annotated, err = utils.parse_annotations_filter(
        request.args.get("exclude_false_positives"), request.args.get("exclude_annotated")
    )
    if err:
        return jsonify(err), 400

    date = f"{year}-{month}-{day}"
    conn = index_db.get_connection()
    try:
        if not index_db.recording_exists(conn, date, stream):
            return jsonify({"error": "Recording not found"}), 404
        previous, next_recording = index_db.find_adjacent(
            conn, date, stream, bird_filter, exclude_false_positives, exclude_annotated
        )
    finally:
        conn.close()

    return jsonify({"previous": _to_entry(previous), "next": _to_entry(next_recording)})


def _to_entry(row) -> dict | None:
    if row is None:
        return None
    year, month, day = row["date"].split("-")
    return {"year": year, "month": month, "day": day, "stream": row["stream"]}


@archive_bp.get("/")
def list_archive():
    from_date, err = utils.parse_date(request.args.get("from"), "from")
    if err:
        return jsonify(err), 400

    to_date, err = utils.parse_date(request.args.get("to"), "to")
    if err:
        return jsonify(err), 400

    if from_date > to_date:
        return jsonify({"error": "'from' date must not be after 'to' date"}), 400

    if (to_date - from_date).days + 1 > utils.MAX_RANGE_DAYS:
        return jsonify({"error": f"Date range must not exceed {utils.MAX_RANGE_DAYS} days"}), 400

    bird_filter = utils.parse_bird_filter(request.args.get("birds"))
    exclude_false_positives, exclude_annotated, err = utils.parse_annotations_filter(
        request.args.get("exclude_false_positives"), request.args.get("exclude_annotated")
    )
    if err:
        return jsonify(err), 400

    conn = index_db.get_connection()
    try:
        rows = index_db.list_recordings(
            conn,
            from_date.isoformat(),
            to_date.isoformat(),
            bird_filter,
            exclude_false_positives,
            exclude_annotated,
        )
    finally:
        conn.close()

    result: dict = {}
    for row in rows:
        year_str, month_str, day_str = row["date"].split("-")
        streams = result.setdefault(year_str, {}).setdefault(month_str, {}).setdefault(day_str, {})
        streams[row["stream"]] = {"birds": json.loads(row["birds"] or "[]")}

    return jsonify(result)
