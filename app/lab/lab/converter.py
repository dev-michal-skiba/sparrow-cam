"""Convert archived .ts video files to PNG frames for analysis."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import cv2

from lab.constants import ARCHIVE_DIR, IMAGES_DIR

ProgressCallback = Callable[[int, int, str], None]


def get_unconverted_playlists(
    archive_path: Path = ARCHIVE_DIR,
    images_path: Path = IMAGES_DIR,
) -> list[str]:
    """
    Find archive folders that haven't been converted to images yet.

    Recursively searches archive_path for folders matching the nested structure:
    {year}/{month}/{day}/{folder_name}

    Returns:
        List of relative paths like "2024/01/15/sparrow_cam-1234567890-uuid"
    """
    if not archive_path.exists():
        return []

    images_path.mkdir(parents=True, exist_ok=True)

    unconverted: list[str] = []

    # Walk the nested structure: year/month/day/folder
    for year_dir in sorted(archive_path.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue

        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir() or not month_dir.name.isdigit():
                continue

            for day_dir in sorted(month_dir.iterdir()):
                if not day_dir.is_dir() or not day_dir.name.isdigit():
                    continue

                for folder in sorted(day_dir.iterdir()):
                    if not folder.is_dir():
                        continue

                    # Check if corresponding images folder exists
                    relative_path = f"{year_dir.name}/{month_dir.name}/{day_dir.name}/{folder.name}"
                    images_folder = images_path / relative_path

                    if not images_folder.exists():
                        # Check if there are any .ts files to convert
                        ts_files = list(folder.glob("*.ts"))
                        if ts_files:
                            unconverted.append(relative_path)

    return unconverted


def convert_playlist_to_pngs(
    folder_path: Path,
    images_base_path: Path = IMAGES_DIR,
    on_file_progress: ProgressCallback | None = None,
) -> int:
    """
    Convert all .ts files in folder_path to PNG frames.

    Args:
        folder_path: Absolute path to folder containing .ts files
        images_base_path: Base path for output images
        on_file_progress: Callback(current_file, total_files, filename)

    Returns:
        Number of frames extracted.
    """
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder_path}")
    if not folder_path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {folder_path}")

    ts_files = sorted(folder_path.glob("*.ts"))
    if not ts_files:
        return 0

    # Determine relative path from ARCHIVE_DIR to maintain structure
    try:
        relative_path = folder_path.relative_to(ARCHIVE_DIR)
    except ValueError:
        # Fallback to just the folder name if not under ARCHIVE_DIR
        relative_path = Path(folder_path.name)

    target_folder = images_base_path / relative_path
    target_folder.mkdir(parents=True, exist_ok=True)

    total_frames = 0

    for idx, ts_file in enumerate(ts_files):
        if on_file_progress:
            on_file_progress(idx + 1, len(ts_files), ts_file.name)

        cap = cv2.VideoCapture(str(ts_file))
        if not cap.isOpened():
            continue

        frame_index = 0
        while True:
            success, frame = cap.read()
            if not success:
                break

            output_path = target_folder / f"{ts_file.stem}-{frame_index}.png"
            cv2.imwrite(str(output_path), frame)
            frame_index += 1

        cap.release()
        total_frames += frame_index

    return total_frames


def convert_all_playlists(
    on_playlist_progress: ProgressCallback | None = None,
    on_file_progress: ProgressCallback | None = None,
) -> tuple[int, int]:
    """
    Convert all unconverted playlists to PNG frames.

    Args:
        on_playlist_progress: Callback(current_playlist, total_playlists, playlist_name)
        on_file_progress: Callback(current_file, total_files, filename)

    Returns:
        Tuple of (playlists converted, total frames extracted)
    """
    unconverted = get_unconverted_playlists()
    if not unconverted:
        return 0, 0

    total_frames = 0

    for idx, relative_path in enumerate(unconverted):
        if on_playlist_progress:
            on_playlist_progress(idx + 1, len(unconverted), relative_path)

        folder_path = ARCHIVE_DIR / relative_path
        frames = convert_playlist_to_pngs(
            folder_path,
            on_file_progress=on_file_progress,
        )
        total_frames += frames

    return len(unconverted), total_frames
