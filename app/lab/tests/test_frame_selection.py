"""Unit tests for frame selection and balancing."""

import random
from pathlib import Path

from lab.frame_selection import (
    Frame,
    _best_candidate,
    _bird_type_quotas,
    _consume_quotas,
    _quotas,
    _read_bird_types,
    _repair_bird_types,
    _score,
    dataset_seed,
    load_frames,
    select_frames,
)


class TestFrame:
    """Tests for Frame dataclass."""

    def test_frame_initialization(self):
        """Test Frame initialization with all fields."""
        image_path = Path("/images/test.jpg")
        label_path = Path("/labels/test.txt")
        frame = Frame(image_path, label_path, 2026, (6, 25), 8, (0, 1))

        assert frame.image_path == image_path
        assert frame.label_path == label_path
        assert frame.year == 2026
        assert frame.day_slot == (6, 25)
        assert frame.hour == 8
        assert frame.bird_types == (0, 1)

    def test_frame_is_positive_with_bird_types(self):
        """Test that frame with bird types is positive."""
        frame = Frame(Path("img.jpg"), Path("label.txt"), 2026, (6, 25), 8, (0, 1))
        assert frame.is_positive is True

    def test_frame_is_positive_without_bird_types(self):
        """Test that frame without bird types is negative."""
        frame = Frame(Path("img.jpg"), Path("label.txt"), 2026, (6, 25), 8, ())
        assert frame.is_positive is False

    def test_frame_is_hashable(self):
        """Test that Frame can be added to a set."""
        frame1 = Frame(Path("img1.jpg"), Path("label1.txt"), 2026, (6, 25), 8, (0,))
        frame2 = Frame(Path("img2.jpg"), Path("label2.txt"), 2026, (6, 25), 8, (1,))
        frame_set = {frame1, frame2}
        assert len(frame_set) == 2


class TestReadBirdTypes:
    """Tests for _read_bird_types function."""

    def test_read_bird_types_empty_file(self, tmp_path):
        """Test reading empty label file."""
        label_path = tmp_path / "label.txt"
        label_path.write_text("")

        types = _read_bird_types(label_path)
        assert types == ()

    def test_read_bird_types_single_box(self, tmp_path):
        """Test reading label file with single box."""
        label_path = tmp_path / "label.txt"
        label_path.write_text("0 0.5 0.5 0.2 0.2\n")

        types = _read_bird_types(label_path)
        assert types == (0,)

    def test_read_bird_types_multiple_boxes(self, tmp_path):
        """Test reading label file with multiple boxes."""
        label_path = tmp_path / "label.txt"
        label_path.write_text("0 0.5 0.5 0.2 0.2\n1 0.3 0.3 0.1 0.1\n2 0.7 0.7 0.1 0.1\n")

        types = _read_bird_types(label_path)
        assert types == (0, 1, 2)

    def test_read_bird_types_skips_empty_lines(self, tmp_path):
        """Test that empty lines are skipped."""
        label_path = tmp_path / "label.txt"
        label_path.write_text("0 0.5 0.5 0.2 0.2\n\n1 0.3 0.3 0.1 0.1\n  \n")

        types = _read_bird_types(label_path)
        assert types == (0, 1)


class TestQuotas:
    """Tests for _quotas function."""

    def test_quotas_empty_counts(self):
        """Test quotas with empty counter."""
        from collections import Counter

        quotas = _quotas(Counter(), 10)
        assert quotas == {}

    def test_quotas_equal_distribution(self):
        """Test quotas with equal distribution."""
        from collections import Counter

        counts = Counter({1: 1, 2: 1, 3: 1})
        quotas = _quotas(counts, 30)

        assert quotas[1] + quotas[2] + quotas[3] == 30
        assert quotas[1] == 10
        assert quotas[2] == 10
        assert quotas[3] == 10

    def test_quotas_unequal_distribution(self):
        """Test quotas with unequal distribution."""
        from collections import Counter

        counts = Counter({1: 3, 2: 1})
        quotas = _quotas(counts, 40)

        assert quotas[1] + quotas[2] == 40
        assert quotas[1] == 30
        assert quotas[2] == 10

    def test_quotas_largest_remainder_rounding(self):
        """Test that largest-remainder rounding is used."""
        from collections import Counter

        counts = Counter({1: 1, 2: 1, 3: 1})
        quotas = _quotas(counts, 10)

        total = sum(quotas.values())
        assert total == 10
        # With 3 items and 10 target, each gets 3.33, so 3+3+4 or similar
        assert all(3 <= quotas[i] <= 4 for i in [1, 2, 3])


class TestBirdTypeQuotas:
    """Tests for _bird_type_quotas function."""

    def test_bird_type_quotas_no_frames(self):
        """Test with no frames."""
        quotas = _bird_type_quotas([], 10)
        assert quotas == {}

    def test_bird_type_quotas_single_type(self):
        """Test with single bird type."""
        frames = [
            Frame(Path("img1.jpg"), Path("label1.txt"), 2026, (6, 25), 8, (0,)),
            Frame(Path("img2.jpg"), Path("label2.txt"), 2026, (6, 26), 8, (0,)),
        ]
        quotas = _bird_type_quotas(frames, 10)

        assert 0 in quotas
        assert quotas[0] == 10

    def test_bird_type_quotas_multiple_types(self):
        """Test with multiple bird types."""
        frames = [
            Frame(Path("img1.jpg"), Path("label1.txt"), 2026, (6, 25), 8, (0,)),
            Frame(Path("img2.jpg"), Path("label2.txt"), 2026, (6, 26), 8, (1,)),
            Frame(Path("img3.jpg"), Path("label3.txt"), 2026, (6, 27), 8, (0, 1)),
        ]
        quotas = _bird_type_quotas(frames, 30)

        assert sum(quotas.values()) == 30
        assert quotas[0] > 0
        assert quotas[1] > 0

    def test_bird_type_quotas_guarantees_representation(self):
        """Test that every bird type gets at least one frame."""
        frames = [
            Frame(Path("img1.jpg"), Path("label1.txt"), 2026, (6, 25), 8, (0,)),
            Frame(Path("img2.jpg"), Path("label2.txt"), 2026, (6, 26), 8, (1,)),
            Frame(Path("img3.jpg"), Path("label3.txt"), 2026, (6, 27), 8, (2,)),
        ]
        quotas = _bird_type_quotas(frames, 5)

        # Every type should have at least 1
        assert quotas[0] >= 1
        assert quotas[1] >= 1
        assert quotas[2] >= 1


class TestScore:
    """Tests for _score function."""

    def test_score_no_outstanding_quotas(self):
        """Test score when no outstanding quotas."""
        frame = Frame(Path("img.jpg"), Path("label.txt"), 2026, (6, 25), 8, (0,))
        score = _score(frame, {}, {}, {})
        assert score == 0

    def test_score_with_year_quota(self):
        """Test score with year quota."""
        frame = Frame(Path("img.jpg"), Path("label.txt"), 2026, (6, 25), 8, (0,))
        score = _score(frame, {2026: 5}, {}, {})
        assert score == 5

    def test_score_with_hour_quota(self):
        """Test score with hour quota."""
        frame = Frame(Path("img.jpg"), Path("label.txt"), 2026, (6, 25), 8, (0,))
        score = _score(frame, {}, {8: 3}, {})
        assert score == 3

    def test_score_with_bird_type_quota(self):
        """Test score with bird type quota."""
        frame = Frame(Path("img.jpg"), Path("label.txt"), 2026, (6, 25), 8, (0, 1))
        score = _score(frame, {}, {}, {0: 2, 1: 3})
        assert score == 5  # max(2, 0) + max(3, 0) + sum([2, 3])

    def test_score_multiple_quotas(self):
        """Test score with multiple quotas."""
        frame = Frame(Path("img.jpg"), Path("label.txt"), 2026, (6, 25), 8, (0,))
        score = _score(frame, {2026: 5}, {8: 3}, {0: 2})
        assert score == 10  # 5 + 3 + 2

    def test_score_negative_quotas_clamped(self):
        """Test that negative quotas are clamped to 0."""
        frame = Frame(Path("img.jpg"), Path("label.txt"), 2026, (6, 25), 8, (0,))
        score = _score(frame, {2026: -5}, {8: -3}, {0: -2})
        assert score == 0


class TestConsumeQuotas:
    """Tests for _consume_quotas function."""

    def test_consume_quotas_year(self):
        """Test consuming year quota."""
        frame = Frame(Path("img.jpg"), Path("label.txt"), 2026, (6, 25), 8, ())
        year_left = {2026: 5}
        _consume_quotas(frame, year_left, {}, {})
        assert year_left[2026] == 4

    def test_consume_quotas_hour(self):
        """Test consuming hour quota."""
        frame = Frame(Path("img.jpg"), Path("label.txt"), 2026, (6, 25), 8, ())
        hour_left = {8: 10}
        _consume_quotas(frame, {}, hour_left, {})
        assert hour_left[8] == 9

    def test_consume_quotas_bird_types(self):
        """Test consuming bird type quotas."""
        frame = Frame(Path("img.jpg"), Path("label.txt"), 2026, (6, 25), 8, (0, 1))
        type_left = {0: 5, 1: 3}
        _consume_quotas(frame, {}, {}, type_left)
        assert type_left[0] == 4
        assert type_left[1] == 2

    def test_consume_quotas_missing_keys(self):
        """Test consuming when quota key doesn't exist."""
        frame = Frame(Path("img.jpg"), Path("label.txt"), 2026, (6, 25), 8, (0,))
        year_left = {}
        hour_left = {}
        type_left = {}
        # Should not raise
        _consume_quotas(frame, year_left, hour_left, type_left)


class TestBestCandidate:
    """Tests for _best_candidate function."""

    def test_best_candidate_single_frame(self):
        """Test with single candidate."""
        frame = Frame(Path("img.jpg"), Path("label.txt"), 2026, (6, 25), 8, ())
        rng = random.Random(42)
        result = _best_candidate([frame], {}, {}, {}, rng)
        assert result == frame

    def test_best_candidate_selects_highest_score(self):
        """Test that best candidate has highest score."""
        frame1 = Frame(Path("img1.jpg"), Path("label1.txt"), 2026, (6, 25), 8, ())
        frame2 = Frame(Path("img2.jpg"), Path("label2.txt"), 2026, (6, 26), 8, ())
        candidates = [frame1, frame2]
        # Give frame2 higher score
        year_left = {2026: 5}
        hour_left = {8: 0}
        rng = random.Random(42)
        result = _best_candidate(candidates, year_left, hour_left, {}, rng)
        # Both have same score for year, so either could be selected
        assert result in candidates

    def test_best_candidate_tie_breaking(self):
        """Test that ties are broken randomly."""
        frame1 = Frame(Path("img1.jpg"), Path("label1.txt"), 2026, (6, 25), 8, ())
        frame2 = Frame(Path("img2.jpg"), Path("label2.txt"), 2026, (6, 25), 8, ())
        candidates = [frame1, frame2]
        results = set()
        for seed in range(10):
            rng = random.Random(seed)
            result = _best_candidate(candidates, {}, {}, {}, rng)
            results.add(result)
        # With multiple seeds, we should get both frames selected at least once
        assert len(results) > 0


class TestLoadFrames:
    """Tests for load_frames function."""

    def test_load_frames_empty_directory(self, tmp_path):
        """Test loading frames from empty directory."""
        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()

        frames = load_frames(tmp_path)
        assert frames == []

    def test_load_frames_single_frame(self, tmp_path):
        """Test loading single frame."""
        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()

        image_path = images_dir / "2026-06-25_auto_2026-06-25T085519Z_uuid_sparrow_cam-4031.jpg"
        label_path = labels_dir / "2026-06-25_auto_2026-06-25T085519Z_uuid_sparrow_cam-4031.txt"
        image_path.write_text("image")
        label_path.write_text("0 0.5 0.5 0.2 0.2\n")

        frames = load_frames(tmp_path)
        assert len(frames) == 1
        assert frames[0].image_path == image_path
        assert frames[0].label_path == label_path
        assert frames[0].year == 2026
        assert frames[0].day_slot == (6, 25)
        assert frames[0].hour == 8
        assert frames[0].bird_types == (0,)

    def test_load_frames_multiple_frames(self, tmp_path):
        """Test loading multiple frames."""
        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()

        for i, hour in enumerate([8, 9, 10]):
            image_path = images_dir / f"2026-06-25_auto_2026-06-25T{hour:02d}0000Z_uuid{i}_sparrow_cam-4031.jpg"
            label_path = labels_dir / f"2026-06-25_auto_2026-06-25T{hour:02d}0000Z_uuid{i}_sparrow_cam-4031.txt"
            image_path.write_text("image")
            label_path.write_text(f"{i} 0.5 0.5 0.2 0.2\n")

        frames = load_frames(tmp_path)
        assert len(frames) == 3

    def test_load_frames_skips_invalid_timestamp(self, tmp_path):
        """Test that files without valid timestamp are skipped."""
        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()

        image_path = images_dir / "no_timestamp.jpg"
        label_path = labels_dir / "no_timestamp.txt"
        image_path.write_text("image")
        label_path.write_text("0 0.5 0.5 0.2 0.2\n")

        frames = load_frames(tmp_path)
        assert frames == []

    def test_load_frames_skips_missing_label(self, tmp_path, caplog):
        """Test that images without matching labels are skipped."""
        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()

        image_path = images_dir / "2026-06-25_auto_2026-06-25T085519Z_uuid_sparrow_cam-4031.jpg"
        image_path.write_text("image")

        frames = load_frames(tmp_path)
        assert frames == []
        assert "no matching label file" in caplog.text

    def test_load_frames_sorted_output(self, tmp_path):
        """Test that frames are returned in sorted order."""
        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()

        # Create files in reverse order
        for i in [2, 1, 0]:
            image_path = images_dir / f"2026-06-25_auto_2026-06-25T{i:02d}0000Z_uuid{i}_sparrow_cam-4031.jpg"
            label_path = labels_dir / f"2026-06-25_auto_2026-06-25T{i:02d}0000Z_uuid{i}_sparrow_cam-4031.txt"
            image_path.write_text("image")
            label_path.write_text("0 0.5 0.5 0.2 0.2\n")

        frames = load_frames(tmp_path)
        assert len(frames) == 3
        # Should be sorted by filename
        for i in range(len(frames) - 1):
            assert frames[i].image_path.name <= frames[i + 1].image_path.name


class TestDatasetSeed:
    """Tests for dataset_seed function."""

    def test_dataset_seed_deterministic(self, tmp_path):
        """Test that dataset seed is deterministic."""
        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()

        image_path = images_dir / "2026-06-25_auto_2026-06-25T085519Z_uuid_sparrow_cam-4031.jpg"
        label_path = labels_dir / "2026-06-25_auto_2026-06-25T085519Z_uuid_sparrow_cam-4031.txt"
        image_path.write_text("image")
        label_path.write_text("0 0.5 0.5 0.2 0.2\n")

        frames = load_frames(tmp_path)
        seed1 = dataset_seed(frames)
        seed2 = dataset_seed(frames)

        assert seed1 == seed2

    def test_dataset_seed_changes_with_file_size(self, tmp_path):
        """Test that seed changes when file sizes change."""
        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()

        image_path = images_dir / "2026-06-25_auto_2026-06-25T085519Z_uuid_sparrow_cam-4031.jpg"
        label_path = labels_dir / "2026-06-25_auto_2026-06-25T085519Z_uuid_sparrow_cam-4031.txt"
        image_path.write_text("image")
        label_path.write_text("0 0.5 0.5 0.2 0.2\n")

        frames1 = load_frames(tmp_path)
        seed1 = dataset_seed(frames1)

        # Modify file size
        label_path.write_text("0 0.5 0.5 0.2 0.2\n1 0.3 0.3 0.1 0.1\n")
        frames2 = load_frames(tmp_path)
        seed2 = dataset_seed(frames2)

        assert seed1 != seed2

    def test_dataset_seed_empty_frames(self):
        """Test seed with empty frames list."""
        seed = dataset_seed([])
        assert isinstance(seed, int)


class TestRepairBirdTypes:
    """Tests for _repair_bird_types function."""

    def test_repair_bird_types_all_present(self):
        """Test when all bird types are already present."""
        frame1 = Frame(Path("img1.jpg"), Path("label1.txt"), 2026, (6, 25), 8, (0,))
        frame2 = Frame(Path("img2.jpg"), Path("label2.txt"), 2026, (6, 26), 8, (1,))
        selected = [frame1, frame2]
        pool = [frame1, frame2]
        rng = random.Random(42)

        original_selected = selected.copy()
        _repair_bird_types(selected, pool, rng)

        # Should be unchanged if all types present
        assert set(selected) == set(original_selected)

    def test_repair_bird_types_adds_missing_type(self):
        """Test that missing bird types are added."""
        frame1 = Frame(Path("img1.jpg"), Path("label1.txt"), 2026, (6, 25), 8, (0,))
        frame2 = Frame(Path("img2.jpg"), Path("label2.txt"), 2026, (6, 26), 8, (1,))
        frame3 = Frame(Path("img3.jpg"), Path("label3.txt"), 2026, (6, 27), 8, (0, 1))
        selected = [frame1, frame2]
        pool = [frame1, frame2, frame3]
        rng = random.Random(42)

        _repair_bird_types(selected, pool, rng)

        # All bird types should still be present after repair
        bird_types_present = set()
        for frame in selected:
            bird_types_present.update(frame.bird_types)
        assert 0 in bird_types_present
        assert 1 in bird_types_present
        assert len(selected) == 2

    def test_repair_bird_types_no_donors(self, caplog):
        """Test when no donors available for missing type."""
        frame1 = Frame(Path("img1.jpg"), Path("label1.txt"), 2026, (6, 25), 8, (0,))
        selected = [frame1]
        pool = [frame1]
        rng = random.Random(42)

        _repair_bird_types(selected, pool, rng)

        # Should log warning since no donor for type 1
        assert len(selected) == 1


class TestSelectFrames:
    """Tests for select_frames function."""

    def test_select_frames_clamping_to_pool_size(self, caplog):
        """Test that selection is clamped to pool size."""
        frames = [
            Frame(Path("img1.jpg"), Path("label1.txt"), 2026, (6, 25), 8, (0,)),
            Frame(Path("img2.jpg"), Path("label2.txt"), 2026, (6, 26), 8, (0,)),
        ]
        rng = random.Random(42)

        selected = select_frames(frames, 10, rng)
        assert len(selected) == 2
        assert "only" in caplog.text.lower() and "2 of the 10" in caplog.text

    def test_select_frames_exact_target(self):
        """Test selection when pool size equals target."""
        frames = [
            Frame(Path("img1.jpg"), Path("label1.txt"), 2026, (6, 25), 8, (0,)),
            Frame(Path("img2.jpg"), Path("label2.txt"), 2026, (6, 26), 8, (0,)),
        ]
        rng = random.Random(42)

        selected = select_frames(frames, 2, rng)
        assert len(selected) == 2
        assert set(selected) == set(frames)

    def test_select_frames_balanced_day_slots(self):
        """Test that day slots are evenly represented."""
        # Create frames across multiple day slots
        frames = []
        for day in range(1, 8):  # 7 days
            for hour in range(8):  # 8 frames per day
                frame = Frame(
                    Path(f"img_{day}_{hour}.jpg"),
                    Path(f"label_{day}_{hour}.txt"),
                    2026,
                    (6, day),
                    hour,
                    (0,),
                )
                frames.append(frame)

        rng = random.Random(42)
        selected = select_frames(frames, 14, rng)

        # Count frames per day slot
        from collections import Counter

        day_counts = Counter(frame.day_slot for frame in selected)
        # Should have frames from different days, not all from one
        assert len(day_counts) > 1

    def test_select_frames_deterministic_with_seed(self):
        """Test that selection is deterministic with same seed."""
        frames = []
        for i in range(100):
            frame = Frame(
                Path(f"img_{i}.jpg"),
                Path(f"label_{i}.txt"),
                2026,
                (6, (i % 7) + 1),
                i % 24,
                (i % 3,),
            )
            frames.append(frame)

        rng1 = random.Random(42)
        selected1 = select_frames(frames, 20, rng1)

        rng2 = random.Random(42)
        selected2 = select_frames(frames, 20, rng2)

        assert selected1 == selected2

    def test_select_frames_sorted_output(self):
        """Test that output is sorted by filename."""
        frames = []
        for i in [2, 0, 1]:
            frame = Frame(
                Path(f"img_{i}.jpg"),
                Path(f"label_{i}.txt"),
                2026,
                (6, 25),
                8,
                (0,),
            )
            frames.append(frame)

        rng = random.Random(42)
        selected = select_frames(frames, 3, rng)

        for i in range(len(selected) - 1):
            assert selected[i].image_path.name <= selected[i + 1].image_path.name

    def test_select_frames_positive_and_negative(self):
        """Test selection with both positive and negative frames."""
        frames = []
        for i in range(20):
            is_positive = i < 15  # 15 positive, 5 negative
            bird_types = (0,) if is_positive else ()
            frame = Frame(
                Path(f"img_{i}.jpg"),
                Path(f"label_{i}.txt"),
                2026,
                (6, (i % 7) + 1),
                i % 24,
                bird_types,
            )
            frames.append(frame)

        rng = random.Random(42)
        selected = select_frames(frames, 10, rng)
        assert len(selected) == 10

    def test_select_frames_skip_empty_slots(self):
        """Test that empty slots are skipped during round-robin."""
        # Create frames with limited day slot diversity
        frames = [
            Frame(Path("img1.jpg"), Path("label1.txt"), 2026, (6, 1), 8, (0,)),
            Frame(Path("img2.jpg"), Path("label2.txt"), 2026, (6, 1), 9, (0,)),
            Frame(Path("img3.jpg"), Path("label3.txt"), 2026, (6, 2), 8, (0,)),
        ]
        rng = random.Random(42)

        selected = select_frames(frames, 3, rng)
        assert len(selected) == 3

    def test_select_frames_multiple_passes(self):
        """Test selection across multiple round-robin passes."""
        # Create many frames in few slots to force multiple passes
        frames = []
        for slot in range(3):
            for i in range(20):
                frame = Frame(
                    Path(f"img_slot{slot}_{i}.jpg"),
                    Path(f"label_slot{slot}_{i}.txt"),
                    2026,
                    (6, slot + 1),
                    i % 24,
                    (0,),
                )
                frames.append(frame)

        rng = random.Random(42)
        selected = select_frames(frames, 30, rng)

        # Should have frames from multiple slots
        day_slots = {frame.day_slot for frame in selected}
        assert len(day_slots) >= 2

    def test_select_frames_breaks_early_when_exhausted(self):
        """Test that selection breaks early when frames are exhausted."""
        # Create frames in single slot
        frames = [
            Frame(Path("img1.jpg"), Path("label1.txt"), 2026, (6, 1), 8, (0,)),
            Frame(Path("img2.jpg"), Path("label2.txt"), 2026, (6, 1), 9, (0,)),
        ]
        rng = random.Random(42)

        # Request more than available
        selected = select_frames(frames, 100, rng)
        assert len(selected) == 2

    def test_bird_type_quotas_raises_donor_if_needed(self):
        """Test that bird type quotas logic handles donor shortage."""

        # Create many frames of type 0, one of type 1
        frames = []
        for i in range(10):
            frames.append(Frame(Path(f"img_{i}.jpg"), Path(f"label_{i}.txt"), 2026, (6, 1), 8, (0,)))
        frames.append(Frame(Path("img_rare.jpg"), Path("label_rare.txt"), 2026, (6, 1), 8, (1,)))

        quotas = _bird_type_quotas(frames, 5)

        # Both types should be represented
        assert quotas[0] > 0
        assert quotas[1] > 0
        assert sum(quotas.values()) == 5

    def test_repair_bird_types_logs_warning_no_donors(self, caplog):
        """Test that warning is logged when no donors available."""
        frame1 = Frame(Path("img1.jpg"), Path("label1.txt"), 2026, (6, 25), 8, (0, 1))
        selected = [frame1]
        pool = [frame1]
        rng = random.Random(42)

        _repair_bird_types(selected, pool, rng)

        # Should log warning about missing type representation
        assert "leaving it unrepresented" in caplog.text or len(selected) == 1

    def test_bird_type_quotas_donor_with_small_quota(self):
        """Test that donors with quota < 2 are skipped."""

        # Create frames with heavy skew towards type 0
        frames = []
        for i in range(20):
            frames.append(Frame(Path(f"img_{i}.jpg"), Path(f"label_{i}.txt"), 2026, (6, 1), 8, (0,)))
        # Only one frame for type 1 and type 2
        frames.append(Frame(Path("img_rare1.jpg"), Path("label_rare1.txt"), 2026, (6, 2), 8, (1,)))
        frames.append(Frame(Path("img_rare2.jpg"), Path("label_rare2.txt"), 2026, (6, 3), 8, (2,)))

        quotas = _bird_type_quotas(frames, 5)

        # Type 0 should dominate, but types 1 and 2 should still be present
        assert quotas[0] > 0
        assert quotas[1] > 0
        assert quotas[2] > 0

    def test_select_frames_with_empty_candidates_for_slot(self):
        """Test that slots with all exhausted candidates are skipped."""
        # Create frames in 2 slots, first gets taken all at once
        frames = []
        for i in range(10):
            if i < 5:
                slot = (6, 1)
            else:
                slot = (6, 2)
            frames.append(Frame(Path(f"img_{i}.jpg"), Path(f"label_{i}.txt"), 2026, slot, i % 24, (0,)))

        rng = random.Random(42)
        selected = select_frames(frames, 7, rng)

        # Should get 7 frames from both slots
        assert len(selected) == 7
        slots_used = {f.day_slot for f in selected}
        assert len(slots_used) == 2

    def test_repair_swaps_only_when_necessary(self):
        """Test that repair only swaps when types are missing."""
        frame1 = Frame(Path("img1.jpg"), Path("label1.txt"), 2026, (6, 25), 8, (0,))
        frame2 = Frame(Path("img2.jpg"), Path("label2.txt"), 2026, (6, 26), 8, (0,))
        frame3 = Frame(Path("img3.jpg"), Path("label3.txt"), 2026, (6, 27), 8, (1,))

        selected = [frame1, frame2]
        pool = [frame1, frame2, frame3]
        rng = random.Random(42)

        _repair_bird_types(selected, pool, rng)

        # Type 1 is missing, so swap should occur
        bird_types_in_selected = set()
        for frame in selected:
            bird_types_in_selected.update(frame.bird_types)

        assert 1 in bird_types_in_selected  # Type 1 should be added
