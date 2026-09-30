import json
import sqlite3

VALID_ROI = {"bird_class": "great_tit", "bbox": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.3}}
VALID_BODY = {"manual_annotations": {"seg1.ts": [VALID_ROI]}}


def insert_recording(archive_root, year, month, day, stream_name, detections=None):
    """Insert a recording entry into the database."""
    date = f"{year}-{month}-{day}"
    conn = sqlite3.connect(archive_root / "index.db")
    conn.execute(
        "INSERT OR IGNORE INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
        (date, stream_name, json.dumps(detections or {}), json.dumps([])),
    )
    conn.commit()
    conn.close()


class TestUpdateMeta:
    def test_missing_year(self, client):
        c, _ = client
        resp = c.patch("/meta?month=01&day=15&stream=stream_a", json=VALID_BODY)
        assert resp.status_code == 400
        assert "Missing required parameters" in resp.get_json()["error"]

    def test_missing_month(self, client):
        c, _ = client
        resp = c.patch("/meta?year=2025&day=15&stream=stream_a", json=VALID_BODY)
        assert resp.status_code == 400

    def test_missing_day(self, client):
        c, _ = client
        resp = c.patch("/meta?year=2025&month=01&stream=stream_a", json=VALID_BODY)
        assert resp.status_code == 400

    def test_missing_stream(self, client):
        c, _ = client
        resp = c.patch("/meta?year=2025&month=01&day=15", json=VALID_BODY)
        assert resp.status_code == 400

    def test_recording_not_found(self, client):
        c, _ = client
        resp = c.patch("/meta?year=2025&month=01&day=15&stream=nonexistent", json=VALID_BODY)
        assert resp.status_code == 404
        assert "Recording not found" in resp.get_json()["error"]

    def test_invalid_body_missing_field(self, client):
        c, archive_root = client
        stream_path = archive_root / "2025" / "01" / "15" / "stream_a"
        stream_path.mkdir(parents=True, exist_ok=True)
        insert_recording(archive_root, "2025", "01", "15", "stream_a")
        resp = c.patch("/meta?year=2025&month=01&day=15&stream=stream_a", json={"wrong_field": "value"})
        assert resp.status_code == 422

    def test_invalid_bird_class(self, client):
        c, archive_root = client
        stream_path = archive_root / "2025" / "01" / "15" / "stream_a"
        stream_path.mkdir(parents=True, exist_ok=True)
        insert_recording(archive_root, "2025", "01", "15", "stream_a")
        body = {
            "manual_annotations": {
                "seg1.ts": [{"bird_class": "unknown_bird", "bbox": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.3}}]
            }
        }
        resp = c.patch("/meta?year=2025&month=01&day=15&stream=stream_a", json=body)
        assert resp.status_code == 422

    def test_invalid_bbox_exceeds_frame(self, client):
        c, archive_root = client
        stream_path = archive_root / "2025" / "01" / "15" / "stream_a"
        stream_path.mkdir(parents=True, exist_ok=True)
        insert_recording(archive_root, "2025", "01", "15", "stream_a")
        body = {
            "manual_annotations": {
                "seg1.ts": [{"bird_class": "great_tit", "bbox": {"x": 0.9, "y": 0.9, "width": 0.5, "height": 0.5}}]
            }
        }
        resp = c.patch("/meta?year=2025&month=01&day=15&stream=stream_a", json=body)
        assert resp.status_code == 422

    def test_adds_manual_annotations_to_new_meta(self, client):
        c, archive_root = client
        stream_path = archive_root / "2025" / "01" / "15" / "stream_a"
        stream_path.mkdir(parents=True, exist_ok=True)
        insert_recording(archive_root, "2025", "01", "15", "stream_a")

        resp = c.patch("/meta?year=2025&month=01&day=15&stream=stream_a", json=VALID_BODY)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["manual_annotations"] == {"seg1.ts": [VALID_ROI]}

    def test_replaces_existing_manual_annotations(self, client):
        c, archive_root = client
        stream_path = archive_root / "2025" / "01" / "15" / "stream_a"
        stream_path.mkdir(parents=True, exist_ok=True)
        insert_recording(archive_root, "2025", "01", "15", "stream_a")
        old_roi = {"bird_class": "pigeon", "bbox": {"x": 0.5, "y": 0.5, "width": 0.1, "height": 0.1}}
        conn = sqlite3.connect(archive_root / "index.db")
        conn.execute(
            "UPDATE recordings SET manual_annotations = ? WHERE date = ? AND stream = ?",
            (json.dumps({"seg2.ts": [old_roi]}), "2025-01-15", "stream_a"),
        )
        conn.commit()
        conn.close()

        resp = c.patch("/meta?year=2025&month=01&day=15&stream=stream_a", json=VALID_BODY)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["manual_annotations"] == {"seg1.ts": [VALID_ROI]}
        assert "seg2.ts" not in data["manual_annotations"]

    def test_preserves_existing_detections(self, client):
        c, archive_root = client
        stream_path = archive_root / "2025" / "01" / "15" / "stream_a"
        stream_path.mkdir(parents=True, exist_ok=True)
        detections = {"seg1.ts": [{"class": "great_tit"}]}
        insert_recording(archive_root, "2025", "01", "15", "stream_a", detections)

        resp = c.patch("/meta?year=2025&month=01&day=15&stream=stream_a", json=VALID_BODY)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["detections"] == detections
        assert data["manual_annotations"] == {"seg1.ts": [VALID_ROI]}

    def test_empty_manual_annotations_allowed(self, client):
        c, archive_root = client
        stream_path = archive_root / "2025" / "01" / "15" / "stream_a"
        stream_path.mkdir(parents=True, exist_ok=True)
        insert_recording(archive_root, "2025", "01", "15", "stream_a")

        resp = c.patch(
            "/meta?year=2025&month=01&day=15&stream=stream_a",
            json={"manual_annotations": {}},
        )
        assert resp.status_code == 200
        assert resp.get_json()["manual_annotations"] == {}

    def test_multiple_rois_per_segment(self, client):
        c, archive_root = client
        stream_path = archive_root / "2025" / "01" / "15" / "stream_a"
        stream_path.mkdir(parents=True, exist_ok=True)
        insert_recording(archive_root, "2025", "01", "15", "stream_a")
        roi_a = {"bird_class": "great_tit", "bbox": {"x": 0.0, "y": 0.0, "width": 0.3, "height": 0.3}}
        roi_b = {"bird_class": "pigeon", "bbox": {"x": 0.5, "y": 0.5, "width": 0.4, "height": 0.4}}
        body = {"manual_annotations": {"seg1.ts": [roi_a, roi_b]}}

        resp = c.patch("/meta?year=2025&month=01&day=15&stream=stream_a", json=body)
        assert resp.status_code == 200
        assert resp.get_json()["manual_annotations"]["seg1.ts"] == [roi_a, roi_b]

    def test_multiple_segments(self, client):
        c, archive_root = client
        stream_path = archive_root / "2025" / "01" / "15" / "stream_a"
        stream_path.mkdir(parents=True, exist_ok=True)
        insert_recording(archive_root, "2025", "01", "15", "stream_a")
        body = {
            "manual_annotations": {
                "seg1.ts": [VALID_ROI],
                "seg2.ts": [{"bird_class": "house_sparrow", "bbox": {"x": 0.2, "y": 0.2, "width": 0.3, "height": 0.3}}],
            }
        }

        resp = c.patch("/meta?year=2025&month=01&day=15&stream=stream_a", json=body)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["manual_annotations"]) == 2
        assert "seg1.ts" in data["manual_annotations"]
        assert "seg2.ts" in data["manual_annotations"]

    def test_eurasian_nuthatch_bird_class(self, client):
        c, archive_root = client
        stream_path = archive_root / "2025" / "01" / "15" / "stream_a"
        stream_path.mkdir(parents=True, exist_ok=True)
        insert_recording(archive_root, "2025", "01", "15", "stream_a")
        body = {
            "manual_annotations": {
                "seg1.ts": [
                    {"bird_class": "eurasian_nuthatch", "bbox": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.3}}
                ]
            }
        }

        resp = c.patch("/meta?year=2025&month=01&day=15&stream=stream_a", json=body)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["manual_annotations"]["seg1.ts"][0]["bird_class"] == "eurasian_nuthatch"

    def test_birds_column_updated_from_annotations(self, client):
        c, archive_root = client
        stream_path = archive_root / "2025" / "01" / "15" / "stream_a"
        stream_path.mkdir(parents=True, exist_ok=True)
        insert_recording(archive_root, "2025", "01", "15", "stream_a")
        body = {
            "manual_annotations": {
                "seg1.ts": [
                    {"bird_class": "great_tit", "bbox": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.3}},
                    {"bird_class": "pigeon", "bbox": {"x": 0.3, "y": 0.3, "width": 0.2, "height": 0.3}},
                ],
                "seg2.ts": [
                    {"bird_class": "great_tit", "bbox": {"x": 0.4, "y": 0.4, "width": 0.1, "height": 0.1}},
                ],
            }
        }

        resp = c.patch("/meta?year=2025&month=01&day=15&stream=stream_a", json=body)
        assert resp.status_code == 200

        # Verify birds column is sorted and unique
        conn = sqlite3.connect(archive_root / "index.db")
        row = conn.execute("SELECT birds FROM recordings WHERE date = '2025-01-15' AND stream = 'stream_a'").fetchone()
        conn.close()
        birds = json.loads(row[0])
        assert birds == ["great_tit", "pigeon"], f"Expected ['great_tit', 'pigeon'], got {birds}"

    def test_patch_updates_database_not_just_response(self, client):
        c, archive_root = client
        stream_path = archive_root / "2025" / "01" / "15" / "stream_a"
        stream_path.mkdir(parents=True, exist_ok=True)
        insert_recording(archive_root, "2025", "01", "15", "stream_a")

        c.patch("/meta?year=2025&month=01&day=15&stream=stream_a", json=VALID_BODY)

        # Verify the database was updated by querying it directly
        conn = sqlite3.connect(archive_root / "index.db")
        row = conn.execute(
            "SELECT manual_annotations, birds FROM recordings WHERE date = '2025-01-15' AND stream = 'stream_a'"
        ).fetchone()
        conn.close()

        assert row is not None
        annotations = json.loads(row[0])
        birds = json.loads(row[1])
        assert annotations == {"seg1.ts": [VALID_ROI]}
        assert "great_tit" in birds

    def test_update_replaces_annotations_and_birds(self, client):
        c, archive_root = client
        stream_path = archive_root / "2025" / "01" / "15" / "stream_a"
        stream_path.mkdir(parents=True, exist_ok=True)

        # Insert a recording with initial annotations
        date = "2025-01-15"
        conn = sqlite3.connect(archive_root / "index.db")
        old_annotations = {
            "seg1.ts": [{"bird_class": "pigeon", "bbox": {"x": 0.5, "y": 0.5, "width": 0.1, "height": 0.1}}]
        }
        conn.execute(
            "INSERT INTO recordings (date, stream, detections, manual_annotations, birds) VALUES (?, ?, ?, ?, ?)",
            (date, "stream_a", "{}", json.dumps(old_annotations), json.dumps(["pigeon"])),
        )
        conn.commit()
        conn.close()

        # Update with new annotations
        new_body = {
            "manual_annotations": {
                "seg2.ts": [{"bird_class": "great_tit", "bbox": {"x": 0.2, "y": 0.2, "width": 0.3, "height": 0.3}}]
            }
        }
        resp = c.patch("/meta?year=2025&month=01&day=15&stream=stream_a", json=new_body)
        assert resp.status_code == 200

        # Verify database has new annotations and birds
        conn = sqlite3.connect(archive_root / "index.db")
        row = conn.execute(
            "SELECT manual_annotations, birds FROM recordings WHERE date = '2025-01-15' AND stream = 'stream_a'"
        ).fetchone()
        conn.close()

        annotations = json.loads(row[0])
        birds = json.loads(row[1])
        assert "seg1.ts" not in annotations
        assert "seg2.ts" in annotations
        assert "pigeon" not in birds
        assert "great_tit" in birds


class TestGetMeta:
    def test_missing_year(self, client):
        c, _ = client
        resp = c.get("/meta?month=01&day=15&stream=stream_a")
        assert resp.status_code == 400
        assert "Missing required parameters" in resp.get_json()["error"]

    def test_missing_month(self, client):
        c, _ = client
        resp = c.get("/meta?year=2025&day=15&stream=stream_a")
        assert resp.status_code == 400

    def test_missing_day(self, client):
        c, _ = client
        resp = c.get("/meta?year=2025&month=01&stream=stream_a")
        assert resp.status_code == 400

    def test_missing_stream(self, client):
        c, _ = client
        resp = c.get("/meta?year=2025&month=01&day=15")
        assert resp.status_code == 400

    def test_recording_not_found(self, client):
        c, _ = client
        resp = c.get("/meta?year=2025&month=01&day=15&stream=nonexistent")
        assert resp.status_code == 404
        assert "Recording not found" in resp.get_json()["error"]

    def test_get_detections_only(self, client):
        c, archive_root = client
        detections = {"seg1.ts": [{"class": "great_tit"}]}
        insert_recording(archive_root, "2025", "01", "15", "stream_a", detections)

        resp = c.get("/meta?year=2025&month=01&day=15&stream=stream_a")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["detections"] == detections
        assert "manual_annotations" not in data

    def test_get_with_manual_annotations(self, client):
        c, archive_root = client
        detections = {"seg1.ts": [{"class": "great_tit"}]}
        annotations = {"seg1.ts": [VALID_ROI]}

        date = "2025-01-15"
        conn = sqlite3.connect(archive_root / "index.db")
        conn.execute(
            "INSERT INTO recordings (date, stream, detections, manual_annotations, birds) VALUES (?, ?, ?, ?, ?)",
            (date, "stream_a", json.dumps(detections), json.dumps(annotations), json.dumps(["great_tit"])),
        )
        conn.commit()
        conn.close()

        resp = c.get("/meta?year=2025&month=01&day=15&stream=stream_a")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["detections"] == detections
        assert data["manual_annotations"] == annotations

    def test_get_empty_detections(self, client):
        c, archive_root = client
        insert_recording(archive_root, "2025", "01", "15", "stream_a", {})

        resp = c.get("/meta?year=2025&month=01&day=15&stream=stream_a")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["detections"] == {}
        assert "manual_annotations" not in data
