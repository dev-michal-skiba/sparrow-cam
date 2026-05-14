import json

VALID_ROI = {"bird_class": "great_tit", "bbox": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.3}}
VALID_BODY = {"manual_annotations": {"seg1.ts": [VALID_ROI]}}


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
        resp = c.patch("/meta?year=2025&month=01&day=15&stream=stream_a", json={"wrong_field": "value"})
        assert resp.status_code == 422

    def test_invalid_bird_class(self, client):
        c, archive_root = client
        stream_path = archive_root / "2025" / "01" / "15" / "stream_a"
        stream_path.mkdir(parents=True, exist_ok=True)
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

        resp = c.patch("/meta?year=2025&month=01&day=15&stream=stream_a", json=VALID_BODY)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["manual_annotations"] == {"seg1.ts": [VALID_ROI]}

    def test_replaces_existing_manual_annotations(self, client):
        c, archive_root = client
        stream_path = archive_root / "2025" / "01" / "15" / "stream_a"
        stream_path.mkdir(parents=True, exist_ok=True)
        old_roi = {"bird_class": "pigeon", "bbox": {"x": 0.5, "y": 0.5, "width": 0.1, "height": 0.1}}
        meta_path = stream_path / "meta.json"
        with meta_path.open("w") as f:
            json.dump({"manual_annotations": {"seg2.ts": [old_roi]}}, f)

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
        meta_path = stream_path / "meta.json"
        with meta_path.open("w") as f:
            json.dump({"detections": detections}, f)

        resp = c.patch("/meta?year=2025&month=01&day=15&stream=stream_a", json=VALID_BODY)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["detections"] == detections
        assert data["manual_annotations"] == {"seg1.ts": [VALID_ROI]}

    def test_meta_file_persisted_to_disk(self, client):
        c, archive_root = client
        stream_path = archive_root / "2025" / "01" / "15" / "stream_a"
        stream_path.mkdir(parents=True, exist_ok=True)

        c.patch("/meta?year=2025&month=01&day=15&stream=stream_a", json=VALID_BODY)

        meta_path = stream_path / "meta.json"
        with meta_path.open() as f:
            saved = json.load(f)
        assert saved["manual_annotations"] == {"seg1.ts": [VALID_ROI]}

    def test_empty_manual_annotations_allowed(self, client):
        c, archive_root = client
        stream_path = archive_root / "2025" / "01" / "15" / "stream_a"
        stream_path.mkdir(parents=True, exist_ok=True)

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
