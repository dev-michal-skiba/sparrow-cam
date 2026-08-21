import pytest

from processor import bird_annotator


@pytest.fixture(autouse=True)
def annotations_path(tmp_path, monkeypatch):
    """Point the annotator at an isolated, temporary annotations file."""
    path = tmp_path / "bird.json"
    monkeypatch.setattr(bird_annotator, "ANNOTATIONS_PATH", str(path))


class TestBirdAnnotator:
    def test_annotate(self):
        annotator = bird_annotator.BirdAnnotator()
        assert annotator._load() == {"version": 1, "detections": {}}
        detections_1 = [{"class": "Pigeon", "confidence": 0.9, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}}]
        detections_2 = []
        annotator.annotate("segment-001.ts", detections_1)
        annotator.annotate("segment-002.ts", detections_2)

        annotations = annotator._load()

        assert annotations == {
            "version": 1,
            "detections": {
                "segment-001.ts": detections_1,
            },
        }

    def test_prune(self):
        annotator = bird_annotator.BirdAnnotator()
        assert annotator._load() == {"version": 1, "detections": {}}
        annotator._write(
            {
                "version": 1,
                "detections": {
                    "keep.ts": [
                        {"class": "Pigeon", "confidence": 0.9, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}}
                    ],
                    "drop.ts": [
                        {"class": "Pigeon", "confidence": 0.8, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}}
                    ],
                },
            }
        )
        assert annotator._load() == {
            "version": 1,
            "detections": {
                "keep.ts": [{"class": "Pigeon", "confidence": 0.9, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}}],
                "drop.ts": [{"class": "Pigeon", "confidence": 0.8, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}}],
            },
        }

        annotator.prune({"keep.ts"})

        assert annotator._load() == {
            "version": 1,
            "detections": {
                "keep.ts": [{"class": "Pigeon", "confidence": 0.9, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}}],
            },
        }

    def test_prune_no_changes(self):
        """Test prune when no segments are removed (removed stays False)."""
        annotator = bird_annotator.BirdAnnotator()
        annotator._write(
            {
                "version": 1,
                "detections": {
                    "keep.ts": [
                        {"class": "Pigeon", "confidence": 0.9, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}}
                    ],
                },
            }
        )

        # Prune with same segments - nothing should be written
        annotator.prune({"keep.ts"})

        annotations = annotator._load()
        assert annotations == {
            "version": 1,
            "detections": {
                "keep.ts": [{"class": "Pigeon", "confidence": 0.9, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}}],
            },
        }

    def test_load_corrupt_json(self, tmp_path, monkeypatch):
        """Test loading a file with invalid JSON."""
        path = tmp_path / "bird.json"
        path.write_text("{invalid json}")
        monkeypatch.setattr(bird_annotator, "ANNOTATIONS_PATH", str(path))

        annotator = bird_annotator.BirdAnnotator()
        result = annotator._load()

        assert result == {"version": 1, "detections": {}}

    def test_load_invalid_format(self, tmp_path, monkeypatch):
        """Test loading a file with valid JSON but invalid format."""
        path = tmp_path / "bird.json"
        path.write_text('{"version": 1}')  # Missing "detections" key
        monkeypatch.setattr(bird_annotator, "ANNOTATIONS_PATH", str(path))

        annotator = bird_annotator.BirdAnnotator()
        result = annotator._load()

        assert result == {"version": 1, "detections": {}}

    def test_load_invalid_format_not_dict(self, tmp_path, monkeypatch):
        """Test loading a file with JSON that's not a dict."""
        path = tmp_path / "bird.json"
        path.write_text('["list", "not", "dict"]')
        monkeypatch.setattr(bird_annotator, "ANNOTATIONS_PATH", str(path))

        annotator = bird_annotator.BirdAnnotator()
        result = annotator._load()

        assert result == {"version": 1, "detections": {}}
