"""Unit tests for lab/annotations.py."""

from unittest.mock import patch

import pytest

from lab.annotations import (
    AnnotationBox,
    DatasetStats,
    _count_split_stats,
    _read_label_file,
    _write_label_file,
    choose_split,
    ensure_dataset_structure,
    find_existing,
    get_annotation_status,
    get_dataset_filename,
    get_dataset_stats,
    load_annotations,
    pixels_to_yolo,
    save_annotations,
    yolo_to_pixels,
)


@pytest.fixture()
def dataset_dir(tmp_path):
    """Patch DATASET_DIR to a temporary directory."""
    with patch("lab.annotations.DATASET_DIR", tmp_path / "dataset"):
        yield tmp_path / "dataset"


@pytest.fixture()
def dataset_with_structure(dataset_dir):
    """Dataset directory with directory structure already created."""
    for split in ("train", "val"):
        (dataset_dir / "images" / split).mkdir(parents=True)
        (dataset_dir / "labels" / split).mkdir(parents=True)
    return dataset_dir


class TestAnnotationBox:
    def test_fields(self):
        box = AnnotationBox(class_id=0, x_center=0.5, y_center=0.5, width=0.2, height=0.3)
        assert box.class_id == 0
        assert box.x_center == 0.5
        assert box.y_center == 0.5
        assert box.width == 0.2
        assert box.height == 0.3


class TestDatasetStats:
    def test_fields(self):
        stats = DatasetStats(
            train_total=10,
            train_positive=7,
            train_negative=3,
            val_total=5,
            val_positive=4,
            val_negative=1,
        )
        assert stats.train_total == 10
        assert stats.val_total == 5


class TestEnsureDatasetStructure:
    def test_creates_directory_tree(self, dataset_dir):
        ensure_dataset_structure()
        assert (dataset_dir / "images" / "train").is_dir()
        assert (dataset_dir / "images" / "val").is_dir()
        assert (dataset_dir / "labels" / "train").is_dir()
        assert (dataset_dir / "labels" / "val").is_dir()

    def test_creates_yaml_file(self, dataset_dir):
        ensure_dataset_structure()
        yaml_path = dataset_dir / "dataset.yaml"
        assert yaml_path.exists()
        content = yaml_path.read_text()
        assert "great_tit" in content

    def test_does_not_overwrite_existing_yaml(self, dataset_dir):
        ensure_dataset_structure()
        yaml_path = dataset_dir / "dataset.yaml"
        yaml_path.write_text("custom content")
        ensure_dataset_structure()
        assert yaml_path.read_text() == "custom content"

    def test_idempotent(self, dataset_dir):
        ensure_dataset_structure()
        ensure_dataset_structure()
        assert (dataset_dir / "images" / "train").is_dir()


class TestGetDatasetFilename:
    def test_returns_combined_stem(self, tmp_path):
        recording = tmp_path / "auto_2026-01-01T000000Z_abc"
        image = recording / "sparrow_cam-100-0.png"
        result = get_dataset_filename(image, recording)
        assert result == "auto_2026-01-01T000000Z_abc_sparrow_cam-100-0"

    def test_uses_image_stem_without_extension(self, tmp_path):
        recording = tmp_path / "rec"
        image = recording / "frame-1-2.png"
        result = get_dataset_filename(image, recording)
        assert result == "rec_frame-1-2"


class TestFindExisting:
    def test_returns_none_when_not_found(self, dataset_with_structure, tmp_path):
        recording = tmp_path / "rec"
        image = recording / "frame-1-0.png"
        assert find_existing(image, recording) is None

    def test_finds_in_train_split(self, dataset_with_structure, tmp_path):
        recording = tmp_path / "rec"
        image = recording / "frame-1-0.png"
        stem = "rec_frame-1-0"
        label = dataset_with_structure / "labels" / "train" / f"{stem}.txt"
        label.write_text("0 0.5 0.5 0.2 0.3")
        result = find_existing(image, recording)
        assert result is not None
        split, boxes = result
        assert split == "train"
        assert len(boxes) == 1

    def test_finds_in_val_split(self, dataset_with_structure, tmp_path):
        recording = tmp_path / "rec"
        image = recording / "frame-1-0.png"
        stem = "rec_frame-1-0"
        label = dataset_with_structure / "labels" / "val" / f"{stem}.txt"
        label.write_text("")
        result = find_existing(image, recording)
        assert result is not None
        split, boxes = result
        assert split == "val"
        assert boxes == []

    def test_finds_negative_annotation(self, dataset_with_structure, tmp_path):
        recording = tmp_path / "rec"
        image = recording / "frame-2-0.png"
        stem = "rec_frame-2-0"
        label = dataset_with_structure / "labels" / "train" / f"{stem}.txt"
        label.write_text("")
        result = find_existing(image, recording)
        assert result is not None
        _, boxes = result
        assert boxes == []


class TestChooseSplit:
    def test_returns_train_or_val(self, dataset_with_structure):
        result = choose_split(is_positive=True)
        assert result in ("train", "val")

    def test_empty_dataset_mostly_returns_train(self, dataset_with_structure):
        results = [choose_split(is_positive=True) for _ in range(100)]
        train_count = results.count("train")
        assert train_count > 50

    def test_corrects_imbalance_toward_val(self, dataset_with_structure):
        """When train is overpopulated, probability should favor val."""
        labels_train = dataset_with_structure / "labels" / "train"
        for i in range(8):
            (labels_train / f"frame-{i}.txt").write_text("0 0.5 0.5 0.2 0.3")

        results = [choose_split(is_positive=True) for _ in range(100)]
        val_count = results.count("val")
        assert val_count > 0

    def test_negative_samples_counted_separately(self, dataset_with_structure):
        """Negative samples use their own counts, independent of positives."""
        labels_train = dataset_with_structure / "labels" / "train"
        for i in range(8):
            (labels_train / f"frame-neg-{i}.txt").write_text("")

        result = choose_split(is_positive=False)
        assert result in ("train", "val")

    def test_prob_clamped_to_zero_when_train_overfull(self, dataset_with_structure):
        """prob_train should be 0 when train already exceeds target."""
        labels_train = dataset_with_structure / "labels" / "train"
        labels_val = dataset_with_structure / "labels" / "val"
        for i in range(9):
            (labels_train / f"frame-{i}.txt").write_text("0 0.5 0.5 0.2 0.3")
        (labels_val / "frame-v.txt").write_text("0 0.5 0.5 0.2 0.3")
        results = [choose_split(is_positive=True) for _ in range(50)]
        val_count = results.count("val")
        assert val_count > 20


class TestSaveAnnotations:
    def test_saves_new_positive_annotation(self, dataset_with_structure, tmp_path):
        recording = tmp_path / "rec"
        recording.mkdir()
        image = recording / "frame-1-0.png"
        image.write_bytes(b"fake image")

        boxes = [AnnotationBox(class_id=0, x_center=0.5, y_center=0.5, width=0.2, height=0.3)]

        with patch("lab.annotations.choose_split", return_value="train"):
            save_annotations(image, recording, boxes)

        stem = "rec_frame-1-0"
        label = dataset_with_structure / "labels" / "train" / f"{stem}.txt"
        img_dest = dataset_with_structure / "images" / "train" / f"{stem}.png"
        assert label.exists()
        assert img_dest.exists()
        content = label.read_text()
        assert "0 0.500000 0.500000 0.200000 0.300000" in content

    def test_saves_new_negative_annotation(self, dataset_with_structure, tmp_path):
        recording = tmp_path / "rec"
        recording.mkdir()
        image = recording / "frame-2-0.png"
        image.write_bytes(b"fake image")

        with patch("lab.annotations.choose_split", return_value="val"):
            save_annotations(image, recording, [])

        stem = "rec_frame-2-0"
        label = dataset_with_structure / "labels" / "val" / f"{stem}.txt"
        assert label.exists()
        assert label.read_text() == ""

    def test_overwrites_existing_label_preserves_split(self, dataset_with_structure, tmp_path):
        recording = tmp_path / "rec"
        recording.mkdir()
        image = recording / "frame-3-0.png"
        image.write_bytes(b"fake image")
        stem = "rec_frame-3-0"

        (dataset_with_structure / "images" / "train").mkdir(parents=True, exist_ok=True)
        (dataset_with_structure / "images" / "train" / f"{stem}.png").write_bytes(b"old image")
        label_path = dataset_with_structure / "labels" / "train" / f"{stem}.txt"
        label_path.write_text("0 0.1 0.1 0.1 0.1")

        new_boxes = [AnnotationBox(class_id=0, x_center=0.9, y_center=0.9, width=0.4, height=0.4)]
        save_annotations(image, recording, new_boxes)

        assert "0.900000" in label_path.read_text()

    def test_creates_structure_if_missing(self, dataset_dir, tmp_path):
        recording = tmp_path / "rec"
        recording.mkdir()
        image = recording / "frame-4-0.png"
        image.write_bytes(b"fake")

        with patch("lab.annotations.choose_split", return_value="train"):
            save_annotations(image, recording, [])

        assert (dataset_dir / "labels" / "train").is_dir()


class TestGetAnnotationStatus:
    def test_returns_false_when_not_annotated(self, dataset_with_structure, tmp_path):
        recording = tmp_path / "rec"
        image = recording / "frame-1-0.png"
        assert get_annotation_status(image, recording) == "False"

    def test_returns_true_positive_with_boxes(self, dataset_with_structure, tmp_path):
        recording = tmp_path / "rec"
        image = recording / "frame-1-0.png"
        stem = "rec_frame-1-0"
        label = dataset_with_structure / "labels" / "train" / f"{stem}.txt"
        label.write_text("0 0.5 0.5 0.2 0.3")
        assert get_annotation_status(image, recording) == "True [positive]"

    def test_returns_true_negative_empty_label(self, dataset_with_structure, tmp_path):
        recording = tmp_path / "rec"
        image = recording / "frame-1-0.png"
        stem = "rec_frame-1-0"
        label = dataset_with_structure / "labels" / "val" / f"{stem}.txt"
        label.write_text("")
        assert get_annotation_status(image, recording) == "True [negative]"


class TestLoadAnnotations:
    def test_returns_empty_list_when_not_found(self, dataset_with_structure, tmp_path):
        recording = tmp_path / "rec"
        image = recording / "frame-1-0.png"
        assert load_annotations(image, recording) == []

    def test_returns_boxes(self, dataset_with_structure, tmp_path):
        recording = tmp_path / "rec"
        image = recording / "frame-1-0.png"
        stem = "rec_frame-1-0"
        label = dataset_with_structure / "labels" / "train" / f"{stem}.txt"
        label.write_text("0 0.5 0.5 0.2 0.3")
        boxes = load_annotations(image, recording)
        assert len(boxes) == 1
        assert boxes[0].class_id == 0

    def test_returns_empty_list_for_negative_annotation(self, dataset_with_structure, tmp_path):
        recording = tmp_path / "rec"
        image = recording / "frame-1-0.png"
        stem = "rec_frame-1-0"
        label = dataset_with_structure / "labels" / "val" / f"{stem}.txt"
        label.write_text("")
        assert load_annotations(image, recording) == []


class TestGetDatasetStats:
    def test_empty_dataset(self, dataset_with_structure):
        stats = get_dataset_stats()
        assert stats.train_total == 0
        assert stats.val_total == 0

    def test_counts_correctly(self, dataset_with_structure):
        labels_train = dataset_with_structure / "labels" / "train"
        labels_val = dataset_with_structure / "labels" / "val"
        (labels_train / "pos1.txt").write_text("0 0.5 0.5 0.2 0.3")
        (labels_train / "pos2.txt").write_text("0 0.1 0.1 0.1 0.1")
        (labels_train / "neg1.txt").write_text("")
        (labels_val / "pos3.txt").write_text("0 0.5 0.5 0.2 0.3")
        (labels_val / "neg2.txt").write_text("")

        stats = get_dataset_stats()
        assert stats.train_total == 3
        assert stats.train_positive == 2
        assert stats.train_negative == 1
        assert stats.val_total == 2
        assert stats.val_positive == 1
        assert stats.val_negative == 1


class TestPixelsToYolo:
    def test_center_box(self):
        box = pixels_to_yolo(40, 30, 60, 70, img_width=100, img_height=100)
        assert box.x_center == pytest.approx(0.5)
        assert box.y_center == pytest.approx(0.5)
        assert box.width == pytest.approx(0.2)
        assert box.height == pytest.approx(0.4)
        assert box.class_id == 0

    def test_custom_class_id(self):
        box = pixels_to_yolo(0, 0, 100, 100, img_width=200, img_height=200, class_id=3)
        assert box.class_id == 3

    def test_full_frame(self):
        box = pixels_to_yolo(0, 0, 100, 100, img_width=100, img_height=100)
        assert box.x_center == pytest.approx(0.5)
        assert box.y_center == pytest.approx(0.5)
        assert box.width == pytest.approx(1.0)
        assert box.height == pytest.approx(1.0)

    def test_reversed_coordinates(self):
        box = pixels_to_yolo(60, 70, 40, 30, img_width=100, img_height=100)
        assert box.width == pytest.approx(0.2)
        assert box.height == pytest.approx(0.4)


class TestYoloToPixels:
    def test_center_box(self):
        box = AnnotationBox(class_id=0, x_center=0.5, y_center=0.5, width=0.2, height=0.4)
        x1, y1, x2, y2 = yolo_to_pixels(box, img_width=100, img_height=100)
        assert x1 == 40
        assert y1 == 30
        assert x2 == 60
        assert y2 == 70

    def test_full_frame(self):
        box = AnnotationBox(class_id=0, x_center=0.5, y_center=0.5, width=1.0, height=1.0)
        x1, y1, x2, y2 = yolo_to_pixels(box, img_width=100, img_height=100)
        assert x1 == 0
        assert y1 == 0
        assert x2 == 100
        assert y2 == 100

    def test_roundtrip_pixels_to_yolo_and_back(self):
        box = pixels_to_yolo(10, 20, 50, 80, img_width=100, img_height=100)
        x1, y1, x2, y2 = yolo_to_pixels(box, img_width=100, img_height=100)
        assert x1 == 10
        assert y1 == 20
        assert x2 == 50
        assert y2 == 80


class TestCountSplitStats:
    def test_nonexistent_dir_returns_zeros(self, tmp_path):
        with patch("lab.annotations.DATASET_DIR", tmp_path / "dataset"):
            pos, neg = _count_split_stats("train")
        assert pos == 0
        assert neg == 0

    def test_counts_positive_and_negative(self, dataset_with_structure):
        labels = dataset_with_structure / "labels" / "train"
        (labels / "pos.txt").write_text("0 0.5 0.5 0.2 0.3")
        (labels / "neg.txt").write_text("")
        pos, neg = _count_split_stats("train")
        assert pos == 1
        assert neg == 1

    def test_ignores_non_txt_files(self, dataset_with_structure):
        labels = dataset_with_structure / "labels" / "train"
        (labels / "image.png").write_bytes(b"")
        pos, neg = _count_split_stats("train")
        assert pos == 0
        assert neg == 0


class TestReadLabelFile:
    def test_reads_single_box(self, tmp_path):
        label = tmp_path / "label.txt"
        label.write_text("0 0.5 0.5 0.2 0.3")
        boxes = _read_label_file(label)
        assert len(boxes) == 1
        assert boxes[0].class_id == 0
        assert boxes[0].x_center == pytest.approx(0.5)

    def test_reads_multiple_boxes(self, tmp_path):
        label = tmp_path / "label.txt"
        label.write_text("0 0.1 0.2 0.3 0.4\n1 0.5 0.6 0.7 0.8")
        boxes = _read_label_file(label)
        assert len(boxes) == 2
        assert boxes[1].class_id == 1

    def test_empty_file_returns_empty_list(self, tmp_path):
        label = tmp_path / "label.txt"
        label.write_text("")
        assert _read_label_file(label) == []

    def test_skips_malformed_lines(self, tmp_path):
        label = tmp_path / "label.txt"
        label.write_text("0 0.5 0.5 0.2 0.3\nbad line\n1 0.1 0.2 0.3 0.4")
        boxes = _read_label_file(label)
        assert len(boxes) == 2


class TestWriteLabelFile:
    def test_writes_single_box(self, tmp_path):
        label = tmp_path / "label.txt"
        boxes = [AnnotationBox(class_id=0, x_center=0.5, y_center=0.5, width=0.2, height=0.3)]
        _write_label_file(label, boxes)
        assert label.read_text() == "0 0.500000 0.500000 0.200000 0.300000"

    def test_writes_multiple_boxes(self, tmp_path):
        label = tmp_path / "label.txt"
        boxes = [
            AnnotationBox(class_id=0, x_center=0.1, y_center=0.2, width=0.3, height=0.4),
            AnnotationBox(class_id=1, x_center=0.5, y_center=0.6, width=0.7, height=0.8),
        ]
        _write_label_file(label, boxes)
        lines = label.read_text().splitlines()
        assert len(lines) == 2
        assert lines[0].startswith("0 ")
        assert lines[1].startswith("1 ")

    def test_writes_empty_boxes(self, tmp_path):
        label = tmp_path / "label.txt"
        _write_label_file(label, [])
        assert label.read_text() == ""
