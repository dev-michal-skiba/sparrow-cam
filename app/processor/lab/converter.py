from pathlib import Path

import cv2

from lab.constants import ARCHIVE_DIR, IMAGES_DIR


def get_missing_archive_folders(archive_path: Path = ARCHIVE_DIR, images_path: Path = IMAGES_DIR) -> set[str]:
    """
    Return folder names that exist in the archive but not in images.

    Raises FileNotFoundError if the archive directory is missing.
    Ensures the images directory exists (creates it if needed).
    """
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive directory does not exist: {archive_path}")
    if not archive_path.is_dir():
        raise NotADirectoryError(f"Archive path is not a directory: {archive_path}")

    images_path.mkdir(parents=True, exist_ok=True)

    archive_dirs = {entry.name for entry in archive_path.iterdir() if entry.is_dir()}
    image_dirs = {entry.name for entry in images_path.iterdir() if entry.is_dir()}

    return archive_dirs - image_dirs


def convert_ts_frames_to_pngs(folder_path: Path, images_base_path: Path = IMAGES_DIR) -> None:
    """
    Convert all .ts files in folder_path to PNG frames under images_base_path.

    Each output folder mirrors folder_path's name inside images_base_path.
    PNG names follow: "<ts-file-stem>-<frame_index>.png", starting at 0.
    Prints a warning when no .ts files are found. Uses OpenCV for decoding.
    """
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder_path}")
    if not folder_path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {folder_path}")

    images_base_path.mkdir(parents=True, exist_ok=True)

    ts_files = sorted(folder_path.glob("*.ts"))
    if not ts_files:
        print(f"Warning: no .ts files found in {folder_path}")
        return
    print(f"Converting {len(ts_files)} .ts file(s) to .png file(s)")
    target_folder = images_base_path / folder_path.name
    target_folder.mkdir(parents=True, exist_ok=True)

    for ts_file in ts_files:
        cap = cv2.VideoCapture(str(ts_file))
        if not cap.isOpened():
            print(f"Warning: unable to open video file {ts_file}")
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


def main():
    missing_folders = get_missing_archive_folders()
    if not missing_folders:
        print("All archive folders are already converted.")
        return

    for index, folder_name in enumerate(sorted(missing_folders), start=1):
        print(f"Converting {index} of {len(missing_folders)}: {folder_name}")
        folder_path = ARCHIVE_DIR / folder_name
        try:
            convert_ts_frames_to_pngs(folder_path)
        except Exception:  # keep going on individual folder failures
            print(f"Error converting {folder_path}")
            raise


if __name__ == "__main__":
    main()
