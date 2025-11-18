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
        assert annotator._load() == {}
        annotator.annotate("segment-001.ts", True)
        annotator.annotate("segment-002.ts", False)

        annotations = annotator._load()

        assert annotations == {
            "segment-001.ts": {"bird_detected": True},
            "segment-002.ts": {"bird_detected": False},
        }

    def test_prune(self):
        annotator = bird_annotator.BirdAnnotator()
        assert annotator._load() == {}
        annotator._write(
            {
                "keep.ts": {"bird_detected": True},
                "drop.ts": {"bird_detected": False},
            }
        )
        assert annotator._load() == {
            "keep.ts": {"bird_detected": True},
            "drop.ts": {"bird_detected": False},
        }

        annotator.prune(["keep.ts"])

        assert annotator._load() == {
            "keep.ts": {"bird_detected": True},
        }
