"""Deterministic selection of a balanced training subset from the synced YOLO dataset."""

from __future__ import annotations

import hashlib
import logging
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# UTC timestamp embedded in dataset filenames, e.g.
# 2026-06-25_auto_2026-06-25T085519Z_<uuid>_sparrow_cam-4031.jpg
TIMESTAMP_PATTERN = re.compile(r"_(\d{4})-(\d{2})-(\d{2})T(\d{2})(\d{2})(\d{2})Z_")


@dataclass(frozen=True)
class Frame:
    """A dataset sample: one image, its label file, and the traits selection balances on."""

    image_path: Path
    label_path: Path
    year: int
    # (month, day) rather than a full date: a day slot spans years, so 1st January is
    # picked from a single year no matter how many years the dataset covers.
    day_slot: tuple[int, int]
    hour: int
    bird_types: tuple[int, ...]

    @property
    def is_positive(self) -> bool:
        return bool(self.bird_types)


def load_frames(dataset_dir: Path) -> list[Frame]:
    """Read every image/label pair under the dataset directory."""
    labels_dir = dataset_dir / "labels"

    frames = []
    for image_path in sorted((dataset_dir / "images").glob("*.jpg")):
        match = TIMESTAMP_PATTERN.search(image_path.name)
        if match is None:
            logger.warning(f"Skipping {image_path.name}: no timestamp in filename")
            continue

        label_path = labels_dir / f"{image_path.stem}.txt"
        if not label_path.is_file():
            logger.warning(f"Skipping {image_path.name}: no matching label file")
            continue

        year, month, day, hour = int(match[1]), int(match[2]), int(match[3]), int(match[4])
        frames.append(Frame(image_path, label_path, year, (month, day), hour, _read_bird_types(label_path)))

    return frames


def dataset_seed(frames: list[Frame], salt: str = "") -> int:
    """Derive a seed from the dataset itself so the same dataset always selects the same frames.

    File sizes are folded in so re-annotation on the Pi, which rewrites label files, reseeds.
    An optional salt lets a second pipeline stage pick a different subset from the same dataset;
    the empty default leaves the seed identical to the unsalted call.
    """
    digest = hashlib.sha256()
    if salt:
        digest.update(f"salt:{salt}\n".encode())
    for frame in sorted(frames, key=lambda frame: frame.image_path.name):
        digest.update(f"{frame.image_path.name}:{frame.image_path.stat().st_size}\n".encode())
        digest.update(f"{frame.label_path.name}:{frame.label_path.stat().st_size}\n".encode())
    return int.from_bytes(digest.digest()[:8], "big")


def select_frames(frames: list[Frame], target: int, rng: random.Random) -> list[Frame]:
    """Select `target` frames spread evenly across day slots, honouring year/hour/bird-type mix."""
    if len(frames) <= target:
        if len(frames) < target:
            logger.warning(f"Only {len(frames)} of the {target} requested frame(s) available; selecting all of them")
        return sorted(frames, key=lambda frame: frame.image_path.name)

    year_left = _quotas(Counter(frame.year for frame in frames), target)
    hour_left = _quotas(Counter(frame.hour for frame in frames), target)
    type_left = _bird_type_quotas(frames, target)

    available: dict[tuple[int, int], list[Frame]] = defaultdict(list)
    for frame in frames:
        available[frame.day_slot].append(frame)
    slot_order = sorted(available)
    rng.shuffle(slot_order)

    # Sweep the slots repeatedly, taking one frame per slot per pass, so every day is
    # represented before any day is used twice.
    selected: list[Frame] = []
    while len(selected) < target:
        taken_this_pass = False
        for slot in slot_order:
            if len(selected) == target:
                break
            candidates = available[slot]
            if not candidates:
                continue
            frame = _best_candidate(candidates, year_left, hour_left, type_left, rng)
            candidates.remove(frame)
            selected.append(frame)
            _consume_quotas(frame, year_left, hour_left, type_left)
            taken_this_pass = True
        if not taken_this_pass:
            break

    _repair_bird_types(selected, frames, rng)
    return sorted(selected, key=lambda frame: frame.image_path.name)


def _read_bird_types(label_path: Path) -> tuple[int, ...]:
    """Class ids of every box in a label file; empty for a negative sample."""
    return tuple(int(line.split()[0]) for line in label_path.read_text().splitlines() if line.strip())


def _quotas(counts: Counter, target: int) -> dict:
    """Split `target` across the counted values proportionally, using largest-remainder rounding."""
    total = sum(counts.values())
    if total == 0:
        return {}

    exact = {value: target * count / total for value, count in counts.items()}
    quotas = {value: int(share) for value, share in exact.items()}
    remainder = target - sum(quotas.values())
    by_largest_remainder = sorted(exact, key=lambda value: (-(exact[value] - quotas[value]), value))
    for value in by_largest_remainder[:remainder]:
        quotas[value] += 1
    return quotas


def _bird_type_quotas(frames: list[Frame], target: int) -> dict:
    """Bird-type quotas mirroring the pool, raised so every present type is guaranteed a frame."""
    counts: Counter = Counter()
    for frame in frames:
        counts.update(set(frame.bird_types))
    quotas = _quotas(counts, target)

    for bird_type in sorted(quotas):
        if quotas[bird_type] > 0:
            continue
        donor = max(quotas, key=lambda value: (quotas[value], -value))
        if quotas[donor] < 2:
            continue
        quotas[donor] -= 1
        quotas[bird_type] = 1
    return quotas


def _score(frame: Frame, year_left: dict, hour_left: dict, type_left: dict) -> int:
    """How much of the outstanding quota deficit this frame would close."""
    score = max(year_left.get(frame.year, 0), 0) + max(hour_left.get(frame.hour, 0), 0)
    return score + sum(max(type_left.get(bird_type, 0), 0) for bird_type in set(frame.bird_types))


def _best_candidate(
    candidates: list[Frame], year_left: dict, hour_left: dict, type_left: dict, rng: random.Random
) -> Frame:
    scored = [(_score(frame, year_left, hour_left, type_left), frame) for frame in candidates]
    best = max(score for score, _ in scored)
    return rng.choice([frame for score, frame in scored if score == best])


def _consume_quotas(frame: Frame, year_left: dict, hour_left: dict, type_left: dict) -> None:
    if frame.year in year_left:
        year_left[frame.year] -= 1
    if frame.hour in hour_left:
        hour_left[frame.hour] -= 1
    for bird_type in set(frame.bird_types):
        if bird_type in type_left:
            type_left[bird_type] -= 1


def _repair_bird_types(selected: list[Frame], pool: list[Frame], rng: random.Random) -> None:
    """Swap frames in until every bird type present in the pool appears at least once."""
    chosen = set(selected)

    for bird_type in sorted({bird_type for frame in pool for bird_type in frame.bird_types}):
        if any(bird_type in frame.bird_types for frame in selected):
            continue

        donors = [frame for frame in pool if bird_type in frame.bird_types and frame not in chosen]
        if not donors:
            logger.warning(f"Bird type {bird_type} has no unselected frame; leaving it unrepresented")
            continue
        donor = rng.choice(donors)

        # Evict from the busiest day slot, preferring a frame whose every bird type is
        # abundant enough that dropping it cannot uncover another type.
        slot_counts = Counter(frame.day_slot for frame in selected)
        type_counts: Counter = Counter()
        for frame in selected:
            type_counts.update(set(frame.bird_types))
        evicted = max(
            selected,
            key=lambda frame: (
                slot_counts[frame.day_slot],
                min((type_counts[bird_type] for bird_type in frame.bird_types), default=0),
                frame.image_path.name,
            ),
        )

        selected[selected.index(evicted)] = donor
        chosen.discard(evicted)
        chosen.add(donor)
