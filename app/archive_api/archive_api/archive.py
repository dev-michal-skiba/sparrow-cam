from datetime import timedelta

from flask import Blueprint, jsonify, request

from archive_api import utils

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

    all_streams = []
    if utils.ARCHIVE_PATH.is_dir():
        for year_dir in sorted(utils.ARCHIVE_PATH.iterdir()):
            if not year_dir.is_dir():
                continue
            for month_dir in sorted(year_dir.iterdir()):
                if not month_dir.is_dir():
                    continue
                for day_dir in sorted(month_dir.iterdir()):
                    if not day_dir.is_dir():
                        continue
                    for stream_dir in sorted(day_dir.iterdir()):
                        if stream_dir.is_dir():
                            all_streams.append(
                                {
                                    "year": year_dir.name,
                                    "month": month_dir.name,
                                    "day": day_dir.name,
                                    "stream": stream_dir.name,
                                }
                            )

    current = {"year": year, "month": month, "day": day, "stream": stream}
    try:
        idx = all_streams.index(current)
    except ValueError:
        return jsonify({"error": "Recording not found"}), 404

    def matches_filter(entry: dict) -> bool:
        stream_path = utils.ARCHIVE_PATH / entry["year"] / entry["month"] / entry["day"] / entry["stream"]
        return utils.stream_matches_filter(stream_path, bird_filter) and utils.stream_matches_annotations_filter(
            stream_path, exclude_false_positives, exclude_annotated
        )

    previous = next((s for s in reversed(all_streams[:idx]) if matches_filter(s)), None)
    next_recording = next((s for s in all_streams[idx + 1 :] if matches_filter(s)), None)

    return jsonify({"previous": previous, "next": next_recording})


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

    result: dict = {}
    current = from_date
    while current <= to_date:
        year_str = current.strftime("%Y")
        month_str = current.strftime("%m")
        day_str = current.strftime("%d")

        day_path = utils.ARCHIVE_PATH / year_str / month_str / day_str
        if day_path.is_dir():
            streams = {
                d.name: {"birds": utils.get_stream_birds(d)}
                for d in sorted(day_path.iterdir())
                if d.is_dir()
                and utils.stream_matches_filter(d, bird_filter)
                and utils.stream_matches_annotations_filter(d, exclude_false_positives, exclude_annotated)
            }
            if streams:
                if year_str not in result:
                    result[year_str] = {}
                if month_str not in result[year_str]:
                    result[year_str][month_str] = {}
                result[year_str][month_str][day_str] = streams

        current += timedelta(days=1)

    return jsonify(result)
