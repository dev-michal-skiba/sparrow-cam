import re
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, request

ARCHIVE_PATH = Path("/var/www/html/storage/sparrow_cam/archive")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_RANGE_DAYS = 31

app = Flask(__name__)


def parse_date(value: str | None, param_name: str) -> tuple[date | None, dict | None]:
    if value is None:
        return None, {"error": f"Missing required parameter: {param_name}"}
    if not DATE_PATTERN.match(value):
        return None, {"error": f"Invalid date format for '{param_name}': expected YYYY-MM-DD"}
    try:
        return datetime.strptime(value, "%Y-%m-%d").date(), None
    except ValueError:
        return None, {"error": f"Invalid date value for '{param_name}': {value}"}


@app.get("/")
def list_archive():
    from_date, err = parse_date(request.args.get("from"), "from")
    if err:
        return jsonify(err), 400

    to_date, err = parse_date(request.args.get("to"), "to")
    if err:
        return jsonify(err), 400

    if from_date > to_date:
        return jsonify({"error": "'from' date must not be after 'to' date"}), 400

    if (to_date - from_date).days + 1 > MAX_RANGE_DAYS:
        return jsonify({"error": f"Date range must not exceed {MAX_RANGE_DAYS} days"}), 400

    result: dict = {}
    current = from_date
    while current <= to_date:
        year_str = current.strftime("%Y")
        month_str = current.strftime("%m")
        day_str = current.strftime("%d")

        day_path = ARCHIVE_PATH / year_str / month_str / day_str
        if day_path.is_dir():
            streams = {d.name: {} for d in sorted(day_path.iterdir()) if d.is_dir()}
            if streams:
                if year_str not in result:
                    result[year_str] = {}
                if month_str not in result[year_str]:
                    result[year_str][month_str] = {}
                result[year_str][month_str][day_str] = streams

        current += timedelta(days=1)

    return jsonify(result)
