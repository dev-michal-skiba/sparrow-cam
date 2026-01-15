import functools
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from lab.constants import IMAGE_FILENAME_PATTERN, IMAGES_DIR
from lab.converter import convert_all_playlists
from lab.exception import UserFacingError
from lab.sync import SyncError, SyncManager
from lab.utils import Region, get_annotated_image_bytes
from processor.bird_detector import BirdDetector

MIN_SELECTION_SIZE = 480


class SyncProgressDialog:
    """Modal dialog showing sync and conversion progress with dual progress bars."""

    def __init__(self, parent: tk.Tk) -> None:
        self.parent = parent
        self.cancelled = False
        self._sync_error: str | None = None

        # Create modal dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Syncing Files")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Make dialog non-resizable and centered
        self.dialog.resizable(False, False)
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        # Content frame with padding
        content = tk.Frame(self.dialog, padx=20, pady=20)
        content.pack(fill="both", expand=True)

        # Download section
        self.download_label = tk.Label(content, text="Downloading: Preparing...", anchor="w")
        self.download_label.pack(fill="x", pady=(0, 5))

        self.download_progress = ttk.Progressbar(content, length=400, mode="determinate")
        self.download_progress.pack(fill="x", pady=(0, 15))

        # Conversion section
        self.convert_label = tk.Label(content, text="Converting: Waiting...", anchor="w")
        self.convert_label.pack(fill="x", pady=(0, 5))

        self.convert_progress = ttk.Progressbar(content, length=400, mode="determinate")
        self.convert_progress.pack(fill="x", pady=(0, 15))

        # Status label
        self.status_label = tk.Label(content, text="", anchor="w", fg="#666666")
        self.status_label.pack(fill="x", pady=(0, 10))

        # Cancel button
        self.cancel_btn = tk.Button(content, text="Cancel", command=self._on_cancel)
        self.cancel_btn.pack()

        # Center dialog on parent
        self._center_dialog()

    def _center_dialog(self) -> None:
        """Center the dialog on the parent window."""
        self.dialog.update_idletasks()
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_w = self.parent.winfo_width()
        parent_h = self.parent.winfo_height()
        dialog_w = self.dialog.winfo_width()
        dialog_h = self.dialog.winfo_height()
        x = parent_x + (parent_w - dialog_w) // 2
        y = parent_y + (parent_h - dialog_h) // 2
        self.dialog.geometry(f"+{x}+{y}")

    def _on_cancel(self) -> None:
        """Handle cancel button click."""
        self.cancelled = True
        self.cancel_btn.config(state="disabled")
        self.status_label.config(text="Cancelling...")

    def _on_close(self) -> None:
        """Handle window close button - same as cancel."""
        self._on_cancel()

    def update_download_progress(self, current: int, total: int, filename: str) -> None:
        """Update download progress bar (thread-safe via parent.after)."""
        self.parent.after(0, self._do_update_download, current, total, filename)

    def _do_update_download(self, current: int, total: int, filename: str) -> None:
        if self.dialog.winfo_exists():
            self.download_label.config(text=f"Downloading: {current}/{total} files")
            self.download_progress["maximum"] = total
            self.download_progress["value"] = current
            self.status_label.config(text=filename)

    def update_convert_progress(self, current: int, total: int, name: str) -> None:
        """Update conversion progress bar (thread-safe via parent.after)."""
        self.parent.after(0, self._do_update_convert, current, total, name)

    def _do_update_convert(self, current: int, total: int, name: str) -> None:
        if self.dialog.winfo_exists():
            self.convert_label.config(text=f"Converting: {current}/{total} playlists")
            self.convert_progress["maximum"] = total
            self.convert_progress["value"] = current
            self.status_label.config(text=name)

    def set_download_complete(self, file_count: int) -> None:
        """Mark download phase as complete."""
        self.parent.after(0, self._do_set_download_complete, file_count)

    def _do_set_download_complete(self, file_count: int) -> None:
        if self.dialog.winfo_exists():
            self.download_label.config(text=f"Downloaded: {file_count} files")
            self.download_progress["value"] = self.download_progress["maximum"]

    def set_no_files_to_sync(self) -> None:
        """Show message when no files need syncing."""
        self.parent.after(0, self._do_set_no_files)

    def _do_set_no_files(self) -> None:
        if self.dialog.winfo_exists():
            self.download_label.config(text="No new files to download")
            self.download_progress["value"] = 0
            self.convert_label.config(text="No playlists to convert")
            self.convert_progress["value"] = 0

    def set_error(self, error: str) -> None:
        """Store error message to display after dialog closes."""
        self._sync_error = error

    def get_error(self) -> str | None:
        """Get stored error message, if any."""
        return self._sync_error

    def close(self) -> None:
        """Close the dialog (thread-safe)."""
        self.parent.after(0, self._do_close)

    def _do_close(self) -> None:
        if self.dialog.winfo_exists():
            self.dialog.grab_release()
            self.dialog.destroy()


def handle_user_error(method):
    """
    Decorator that catches UserFacingError exceptions and displays them to the user.

    This decorator should be applied to methods that may raise UserFacingError exceptions.
    The error will be displayed in a popup dialog using tkinter's messagebox.
    """

    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except UserFacingError as exc:
            if exc.severity == "info":
                messagebox.showinfo(exc.title, exc.message)
            else:
                messagebox.showerror(exc.title, exc.message)
            return None

    return wrapper


class LabGUI:
    """Tkinter GUI for selecting PNGs in a storage directory and running detection."""

    def __init__(self) -> None:
        self.detector = BirdDetector()

        # Root
        self.root = tk.Tk()
        self.root.title("Sparrow Cam Lab")
        self.set_window_size()
        self.root.bind("<Configure>", self.on_resize, add="+")
        self.content_pad = 24

        # State
        self.__selected_image: Path | None = None
        self.__image_obj: tk.PhotoImage | None = None
        self.__selected_image_text = tk.StringVar(value="No file selected")

        # Selection state for regions of interest (supports multiple regions)
        self.__selection_start: tuple[int, int] | None = None
        self.__current_rect: int | None = None  # Canvas rectangle ID being drawn
        self.__selection_rects: list[int] = []  # Canvas rectangle IDs for finalized selections
        self.__selection_texts: list[int] = []  # Canvas text IDs for finalized ROI labels
        self.__selection_bgs: list[int] = []  # Canvas rectangle IDs for finalized ROI label backgrounds
        self.__selection_regions: list[tuple[int, int, int, int]] = []  # List of (x1, y1, x2, y2)

        # Crosshair lines for selection guidance
        self.__crosshair_h: int | None = None  # Horizontal line ID
        self.__crosshair_v: int | None = None  # Vertical line ID

        # Dimension label shown while drawing selection
        self.__dimension_text: int | None = None  # Canvas text ID
        self.__dimension_bg: int | None = None  # Canvas rectangle ID for text background

        # Recording navigation state
        self.__current_recording: Path | None = None  # Selected recording folder
        self.__all_recordings: list[Path] = []  # All recordings sorted by date
        self.__frame_files: list[Path] = []  # All PNG files in current recording, sorted
        self.__current_frame_index: int = 0  # Index into frame_files
        self.__frames_per_segment: int = 0  # Frames per segment (calculated from first segment)

        # UI components
        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=(24, 12))

        self.sync_btn = tk.Button(self.button_frame, text="Sync", command=self.start_sync)
        self.sync_btn.pack(side="left", padx=(0, 8))

        self.select_btn = tk.Button(self.button_frame, text="Select recording", command=self.choose_recording)
        self.select_btn.pack(side="left", padx=(0, 8))

        self.detect_btn = tk.Button(self.button_frame, text="Detect Bird", command=self.detect_bird)

        self.clear_btn = tk.Button(self.button_frame, text="Clear", command=self.clear_all)

        # Navigation frame (hidden until recording is loaded)
        self.nav_frame = tk.Frame(self.root)

        # Recording navigation buttons
        self.prev_rec_btn = tk.Button(self.nav_frame, text="< Prev Recording", command=self.prev_recording)
        self.prev_rec_btn.pack(side="left", padx=(0, 8))

        # Frame navigation buttons
        self.nav_minus_5s_btn = tk.Button(self.nav_frame, text="-5s", command=lambda: self.navigate_seconds(-5))
        self.nav_minus_5s_btn.pack(side="left", padx=(0, 2))

        self.nav_minus_1s_btn = tk.Button(self.nav_frame, text="-1s", command=lambda: self.navigate_seconds(-1))
        self.nav_minus_1s_btn.pack(side="left", padx=(0, 2))

        self.nav_minus_5f_btn = tk.Button(self.nav_frame, text="-5f", command=lambda: self.navigate_frames(-5))
        self.nav_minus_5f_btn.pack(side="left", padx=(0, 2))

        self.nav_minus_1f_btn = tk.Button(self.nav_frame, text="-1f", command=lambda: self.navigate_frames(-1))
        self.nav_minus_1f_btn.pack(side="left", padx=(0, 8))

        self.nav_plus_1f_btn = tk.Button(self.nav_frame, text="+1f", command=lambda: self.navigate_frames(1))
        self.nav_plus_1f_btn.pack(side="left", padx=(0, 2))

        self.nav_plus_5f_btn = tk.Button(self.nav_frame, text="+5f", command=lambda: self.navigate_frames(5))
        self.nav_plus_5f_btn.pack(side="left", padx=(0, 2))

        self.nav_plus_1s_btn = tk.Button(self.nav_frame, text="+1s", command=lambda: self.navigate_seconds(1))
        self.nav_plus_1s_btn.pack(side="left", padx=(0, 2))

        self.nav_plus_5s_btn = tk.Button(self.nav_frame, text="+5s", command=lambda: self.navigate_seconds(5))
        self.nav_plus_5s_btn.pack(side="left", padx=(0, 8))

        self.next_rec_btn = tk.Button(self.nav_frame, text="Next Recording >", command=self.next_recording)
        self.next_rec_btn.pack(side="left")

        # Canvas for image preview with selection support
        self.image_canvas = tk.Canvas(self.root, highlightthickness=0)
        self.image_canvas.pack(padx=24, pady=(0, 24))
        self.__canvas_image_id: int | None = None

        # Bind mouse events for selection
        self.image_canvas.bind("<Button-1>", self.on_selection_start)
        self.image_canvas.bind("<B1-Motion>", self.on_selection_drag)
        self.image_canvas.bind("<ButtonRelease-1>", self.on_selection_end)

        # Bind mouse events for crosshair guidance
        self.image_canvas.bind("<Motion>", self.on_mouse_move)
        self.image_canvas.bind("<Leave>", self.on_mouse_leave)

        # Progress bar frame (hidden until recording is loaded)
        self.progress_frame = tk.Frame(self.root)

        # Position label (e.g., "0:02.5 / 0:15.0 (frame 75/450)")
        self.__position_text = tk.StringVar(value="")
        self.position_label = tk.Label(
            self.progress_frame,
            textvariable=self.__position_text,
            fg="#333333",
            font=("TkDefaultFont", 9),
        )
        self.position_label.pack(side="top", pady=(0, 4))

        # Progress bar (ttk.Scale for interactive seeking)
        self.progress_bar = ttk.Scale(
            self.progress_frame,
            from_=0,
            to=100,
            orient="horizontal",
            command=self._on_progress_seek,
        )
        self.progress_bar.pack(fill="x", padx=24)

        self.path_hint = tk.Label(
            self.root,
            textvariable=self.__selected_image_text,
            justify="left",
            fg="#555555",
            font=("TkDefaultFont", 9),
            anchor="w",
        )
        self.path_hint.pack(side="bottom", fill="x", padx=self.content_pad, pady=(0, 12))

    def set_window_size(self) -> None:
        """Set an initial window size to about half the screen and center it."""
        self.root.update_idletasks()  # ensure screen metrics are available
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        width = int(screen_w * 0.55)
        height = int(screen_h * 0.6)
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2

        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(640, 480)

    def on_resize(self, event) -> None:
        """Keep the filename hint spanning the available width."""
        available = max(event.width - 2 * self.content_pad, 200)
        self.path_hint.config(wraplength=available)

    def get_selected_folder_from_user(self) -> Path | None:
        """Open directory dialog to select a recording folder."""
        path = filedialog.askdirectory(
            initialdir=str(IMAGES_DIR),
            title="Select recording",
        )
        return Path(path) if path else None

    def set_selected_image(self, path: Path) -> None:
        self.__selected_image = path.resolve()
        self.__selected_image_text.set(str(self.__selected_image))

    def scan_recording_frames(self, folder: Path) -> list[Path]:
        """
        Scan a recording folder for PNG files and return them sorted by segment then frame.

        Returns list of Path objects sorted by (segment_number, frame_index).
        """
        frames: list[tuple[int, int, Path]] = []

        for png_file in folder.glob("*.png"):
            match = IMAGE_FILENAME_PATTERN.match(png_file.name)
            if match:
                segment = int(match.group(2))
                frame_idx = int(match.group(3))
                frames.append((segment, frame_idx, png_file))

        # Sort by segment number, then frame index
        frames.sort(key=lambda x: (x[0], x[1]))
        return [f[2] for f in frames]

    def calculate_frames_per_segment(self) -> int:
        """Calculate frames per segment from the first segment's frame count."""
        if not self.__frame_files:
            return 0

        # Get the first segment number
        first_match = IMAGE_FILENAME_PATTERN.match(self.__frame_files[0].name)
        if not first_match:
            return 0

        first_segment = int(first_match.group(2))

        # Count frames in first segment
        count = 0
        for frame_file in self.__frame_files:
            match = IMAGE_FILENAME_PATTERN.match(frame_file.name)
            if match and int(match.group(2)) == first_segment:
                count += 1
            elif match:
                # We've moved to the next segment
                break

        return count

    def scan_all_recordings(self) -> list[Path]:
        """
        Scan IMAGES_DIR for all recording folders and return them sorted by path (date order).

        Returns list of recording folder Paths sorted by their full path.
        """
        if not IMAGES_DIR.exists():
            return []

        recordings: list[Path] = []

        # Walk the nested structure: year/month/day/folder
        for year_dir in sorted(IMAGES_DIR.iterdir()):
            if not year_dir.is_dir() or not year_dir.name.isdigit():
                continue

            for month_dir in sorted(year_dir.iterdir()):
                if not month_dir.is_dir() or not month_dir.name.isdigit():
                    continue

                for day_dir in sorted(month_dir.iterdir()):
                    if not day_dir.is_dir() or not day_dir.name.isdigit():
                        continue

                    for folder in sorted(day_dir.iterdir()):
                        if folder.is_dir():
                            # Check if it has PNG files
                            if any(folder.glob("*.png")):
                                recordings.append(folder)

        return recordings

    def show_navigation(self) -> None:
        """Show navigation controls."""
        if not self.nav_frame.winfo_ismapped():
            self.nav_frame.pack(pady=(0, 8))
        if not self.progress_frame.winfo_ismapped():
            self.progress_frame.pack(fill="x", padx=self.content_pad, pady=(0, 8))

    def hide_navigation(self) -> None:
        """Hide navigation controls."""
        if self.nav_frame.winfo_ismapped():
            self.nav_frame.pack_forget()
        if self.progress_frame.winfo_ismapped():
            self.progress_frame.pack_forget()

    def update_progress_display(self) -> None:
        """Update progress bar and position label based on current frame."""
        if not self.__frame_files or self.__frames_per_segment == 0:
            return

        total_frames = len(self.__frame_files)
        current = self.__current_frame_index

        # Calculate current position as seconds and frame within second
        current_second = current // self.__frames_per_segment
        current_frame_in_second = current % self.__frames_per_segment

        # Calculate total duration (last frame position)
        last_frame = total_frames - 1
        total_second = last_frame // self.__frames_per_segment
        total_frame_in_second = last_frame % self.__frames_per_segment

        # Format as XsYf / XsYf
        position_str = f"{current_second}s{current_frame_in_second}f / " f"{total_second}s{total_frame_in_second}f"
        self.__position_text.set(position_str)

        # Update progress bar
        self.progress_bar.config(to=total_frames - 1)
        self.progress_bar.set(current)

    def _on_progress_seek(self, value: str) -> None:
        """Handle progress bar seek."""
        if not self.__frame_files:
            return
        new_index = int(float(value))
        if new_index != self.__current_frame_index:
            self.load_frame(new_index)

    def set_image_preview(self) -> None:
        if self.__image_obj is None:
            return
        # Resize canvas to match image
        width = self.__image_obj.width()
        height = self.__image_obj.height()
        self.image_canvas.config(width=width, height=height)

        # Clear previous image only
        if self.__canvas_image_id is not None:
            self.image_canvas.delete(self.__canvas_image_id)

        # Draw image on canvas
        self.__canvas_image_id = self.image_canvas.create_image(0, 0, anchor="nw", image=self.__image_obj)

        # Raise selection rectangles, ROI backgrounds and texts above the image so they remain visible
        for rect_id in self.__selection_rects:
            self.image_canvas.tag_raise(rect_id)
        for bg_id in self.__selection_bgs:
            self.image_canvas.tag_raise(bg_id)
        for text_id in self.__selection_texts:
            self.image_canvas.tag_raise(text_id)
        if self.__current_rect is not None:
            self.image_canvas.tag_raise(self.__current_rect)
        if self.__dimension_bg is not None:
            self.image_canvas.tag_raise(self.__dimension_bg)
        if self.__dimension_text is not None:
            self.image_canvas.tag_raise(self.__dimension_text)

    def show_detect_button(self) -> None:
        if not self.detect_btn.winfo_ismapped():
            self.detect_btn.pack(side="left")

    def show_clear_button(self) -> None:
        if not self.clear_btn.winfo_ismapped():
            self.clear_btn.pack(side="left", padx=(8, 0))

    def hide_clear_button(self) -> None:
        if self.clear_btn.winfo_ismapped():
            self.clear_btn.pack_forget()

    def on_selection_start(self, event) -> None:
        """Start drawing a new selection rectangle."""
        if self.__image_obj is None:
            return
        self.__selection_start = (event.x, event.y)
        # Create a new rectangle for the current selection
        self.__current_rect = self.image_canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="blue", width=2
        )

    def on_selection_drag(self, event) -> None:
        """Update selection rectangle while dragging (constrained to square)."""
        if self.__selection_start is None or self.__current_rect is None:
            return
        x1, y1 = self.__selection_start
        x2, y2 = event.x, event.y

        # Constrain to square: use the larger dimension for both
        dx = x2 - x1
        dy = y2 - y1
        side = max(abs(dx), abs(dy))
        x2 = x1 + side * (1 if dx >= 0 else -1)
        y2 = y1 + side * (1 if dy >= 0 else -1)

        self.image_canvas.coords(self.__current_rect, x1, y1, x2, y2)

        # Calculate normalized ROI coordinates
        roi_x1, roi_x2 = min(x1, x2), max(x1, x2)
        roi_y1, roi_y2 = min(y1, y2), max(y1, y2)
        # Position text at the top-left corner of the rectangle
        text_x = roi_x1 + 4
        text_y = roi_y1 + 4
        # Show ROI coordinates and size (with min requirement indicator)
        roi_str = f"ROI: ({roi_x1}, {roi_y1}, {roi_x2}, {roi_y2})\nSize: {side}px (min: {MIN_SELECTION_SIZE}px)"

        if self.__dimension_text is None:
            # Create background rectangle first (so it's behind text)
            self.__dimension_bg = self.image_canvas.create_rectangle(
                text_x - 2,
                text_y - 2,
                text_x + 2,
                text_y + 2,
                fill="white",
                outline="",
            )
            self.__dimension_text = self.image_canvas.create_text(
                text_x,
                text_y,
                text=roi_str,
                anchor="nw",
                fill="blue",
                font=("TkDefaultFont", 10, "bold"),
            )
            # Update background to match text size
            bbox = self.image_canvas.bbox(self.__dimension_text)
            if bbox:
                self.image_canvas.coords(self.__dimension_bg, bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2)
        else:
            self.image_canvas.coords(self.__dimension_text, text_x, text_y)
            self.image_canvas.itemconfig(self.__dimension_text, text=roi_str)
            # Update background position and size
            bbox = self.image_canvas.bbox(self.__dimension_text)
            if bbox and self.__dimension_bg is not None:
                self.image_canvas.coords(self.__dimension_bg, bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2)

    def on_selection_end(self, event) -> None:
        """Finalize selection rectangle (constrained to square) and add to the list of regions."""
        if self.__selection_start is None or self.__image_obj is None:
            return

        x1, y1 = self.__selection_start
        x2, y2 = event.x, event.y

        # Constrain to square: use the larger dimension for both
        dx = x2 - x1
        dy = y2 - y1
        side = max(abs(dx), abs(dy))
        x2 = x1 + side * (1 if dx >= 0 else -1)
        y2 = y1 + side * (1 if dy >= 0 else -1)

        # Normalize coordinates (ensure x1 < x2, y1 < y2)
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)

        # Clamp to image bounds
        width = self.__image_obj.width()
        height = self.__image_obj.height()
        x1 = max(0, min(x1, width))
        x2 = max(0, min(x2, width))
        y1 = max(0, min(y1, height))
        y2 = max(0, min(y2, height))

        # Calculate actual side length after clamping
        actual_side = x2 - x1  # Since it's a square, width == height

        # Only add region if selection meets minimum size requirement
        if actual_side >= MIN_SELECTION_SIZE:
            self.__selection_regions.append((x1, y1, x2, y2))
            self.__selection_rects.append(self.__current_rect)
            self.__current_rect = None
            # Keep the ROI text/background and add to finalized lists
            if self.__dimension_text is not None:
                # Update text with clamped coordinates and size
                roi_str = f"ROI: ({x1}, {y1}, {x2}, {y2})\nSize: {actual_side}px"
                self.image_canvas.itemconfig(self.__dimension_text, text=roi_str)
                self.image_canvas.coords(self.__dimension_text, x1 + 4, y1 + 4)
                # Update background position and size
                bbox = self.image_canvas.bbox(self.__dimension_text)
                if bbox and self.__dimension_bg is not None:
                    self.image_canvas.coords(self.__dimension_bg, bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2)
                    self.__selection_bgs.append(self.__dimension_bg)
                    self.__dimension_bg = None
                self.__selection_texts.append(self.__dimension_text)
                self.__dimension_text = None
            self.show_clear_button()
        else:
            # Too small, delete the rectangle and text, show error
            if self.__current_rect is not None:
                self.image_canvas.delete(self.__current_rect)
                self.__current_rect = None
            self.hide_dimension_text()
            messagebox.showerror(
                "Selection too small",
                f"Selection must be at least {MIN_SELECTION_SIZE}x{MIN_SELECTION_SIZE} pixels.\n"
                f"Your selection: {actual_side}x{actual_side} pixels.",
            )

        self.__selection_start = None

    def hide_dimension_text(self) -> None:
        """Remove the dimension text and background from the canvas."""
        if self.__dimension_bg is not None:
            self.image_canvas.delete(self.__dimension_bg)
            self.__dimension_bg = None
        if self.__dimension_text is not None:
            self.image_canvas.delete(self.__dimension_text)
            self.__dimension_text = None

    def on_mouse_move(self, event) -> None:
        """Update crosshair lines to follow the mouse cursor."""
        if self.__image_obj is None:
            return
        # Hide crosshairs while dragging a selection
        if self.__selection_start is not None:
            self.hide_crosshairs()
            return

        width = self.__image_obj.width()
        height = self.__image_obj.height()
        x, y = event.x, event.y

        # Only show crosshairs when cursor is within image bounds
        if not (0 <= x <= width and 0 <= y <= height):
            self.hide_crosshairs()
            return

        # Create or update horizontal line
        if self.__crosshair_h is None:
            self.__crosshair_h = self.image_canvas.create_line(0, y, width, y, fill="blue", width=1, stipple="gray50")
        else:
            self.image_canvas.coords(self.__crosshair_h, 0, y, width, y)
            self.image_canvas.tag_raise(self.__crosshair_h)

        # Create or update vertical line
        if self.__crosshair_v is None:
            self.__crosshair_v = self.image_canvas.create_line(x, 0, x, height, fill="blue", width=1, stipple="gray50")
        else:
            self.image_canvas.coords(self.__crosshair_v, x, 0, x, height)
            self.image_canvas.tag_raise(self.__crosshair_v)

    def on_mouse_leave(self, event) -> None:
        """Hide crosshairs when mouse leaves the canvas."""
        self.hide_crosshairs()

    def hide_crosshairs(self) -> None:
        """Remove crosshair lines from the canvas."""
        if self.__crosshair_h is not None:
            self.image_canvas.delete(self.__crosshair_h)
            self.__crosshair_h = None
        if self.__crosshair_v is not None:
            self.image_canvas.delete(self.__crosshair_v)
            self.__crosshair_v = None

    def clear_all(self) -> None:
        """Clear all selection regions and reset image to remove detection rectangles."""
        # Clear selection rectangles
        if self.__current_rect is not None:
            self.image_canvas.delete(self.__current_rect)
            self.__current_rect = None
        for rect_id in self.__selection_rects:
            self.image_canvas.delete(rect_id)
        self.__selection_rects.clear()
        for bg_id in self.__selection_bgs:
            self.image_canvas.delete(bg_id)
        self.__selection_bgs.clear()
        for text_id in self.__selection_texts:
            self.image_canvas.delete(text_id)
        self.__selection_texts.clear()
        self.__selection_regions.clear()
        self.__selection_start = None
        self.hide_dimension_text()

        # Reset to original image to clear detection rectangles
        if self.__selected_image is not None:
            self.__image_obj = tk.PhotoImage(file=self.__selected_image)
            self.set_image_preview()

        self.hide_clear_button()

    def clear_canvas_elements(self) -> None:
        """Clear all canvas elements but preserve selection regions data."""
        if self.__current_rect is not None:
            self.image_canvas.delete(self.__current_rect)
            self.__current_rect = None
        for rect_id in self.__selection_rects:
            self.image_canvas.delete(rect_id)
        self.__selection_rects.clear()
        for bg_id in self.__selection_bgs:
            self.image_canvas.delete(bg_id)
        self.__selection_bgs.clear()
        for text_id in self.__selection_texts:
            self.image_canvas.delete(text_id)
        self.__selection_texts.clear()
        self.__selection_start = None
        self.hide_dimension_text()

    def redraw_selections(self) -> None:
        """Redraw selection rectangles and labels from saved regions."""
        for x1, y1, x2, y2 in self.__selection_regions:
            # Draw selection rectangle
            rect_id = self.image_canvas.create_rectangle(x1, y1, x2, y2, outline="blue", width=2)
            self.__selection_rects.append(rect_id)

            # Draw background for label
            side = x2 - x1
            roi_str = f"ROI: ({x1}, {y1}, {x2}, {y2})\nSize: {side}px"
            text_id = self.image_canvas.create_text(
                x1 + 4,
                y1 + 4,
                text=roi_str,
                anchor="nw",
                fill="blue",
                font=("TkDefaultFont", 10, "bold"),
            )
            bbox = self.image_canvas.bbox(text_id)
            if bbox:
                bg_id = self.image_canvas.create_rectangle(
                    bbox[0] - 2,
                    bbox[1] - 2,
                    bbox[2] + 2,
                    bbox[3] + 2,
                    fill="white",
                    outline="",
                )
                # Move background behind text
                self.image_canvas.tag_lower(bg_id, text_id)
                self.__selection_bgs.append(bg_id)
            self.__selection_texts.append(text_id)

        if self.__selection_regions:
            self.show_clear_button()

    @handle_user_error
    def choose_recording(self) -> None:
        """Open a folder dialog and load the first frame from the selected recording."""
        folder = self.get_selected_folder_from_user()
        if folder is None:
            return

        # Scan for frame files
        frames = self.scan_recording_frames(folder)
        if not frames:
            messagebox.showerror("Invalid Recording", "No valid PNG frames found in the selected folder.")
            return

        # Update recording state
        self.__current_recording = folder.resolve()
        self.__frame_files = frames
        self.__current_frame_index = 0
        self.__frames_per_segment = self.calculate_frames_per_segment()

        # Scan all recordings for prev/next navigation
        self.__all_recordings = self.scan_all_recordings()

        # Load first frame
        self.load_frame(0)

        # Show navigation controls
        self.show_navigation()
        self.show_detect_button()

    def load_frame(self, index: int) -> None:
        """
        Load a frame at the specified index.

        Clamps index to valid range, preserves selection regions.
        """
        if not self.__frame_files:
            return

        # Clamp index to valid range
        index = max(0, min(index, len(self.__frame_files) - 1))

        # Update current frame index
        self.__current_frame_index = index

        # Load the frame
        frame_path = self.__frame_files[index]
        self.set_selected_image(frame_path)
        self.__image_obj = tk.PhotoImage(file=frame_path)

        # Clear canvas elements but preserve selection regions
        self.clear_canvas_elements()
        self.set_image_preview()

        # Redraw selections on the new image
        self.redraw_selections()

        # Update progress display
        self.update_progress_display()

    def navigate_frames(self, delta: int) -> None:
        """Navigate by a number of frames (positive or negative)."""
        if not self.__frame_files:
            return

        new_index = self.__current_frame_index + delta
        # Clamp to valid range
        new_index = max(0, min(new_index, len(self.__frame_files) - 1))

        if new_index != self.__current_frame_index:
            self.load_frame(new_index)

    def navigate_seconds(self, delta: int) -> None:
        """Navigate by a number of seconds (positive or negative)."""
        if not self.__frame_files or self.__frames_per_segment == 0:
            return

        frame_delta = delta * self.__frames_per_segment
        new_index = self.__current_frame_index + frame_delta
        # Clamp to valid range
        new_index = max(0, min(new_index, len(self.__frame_files) - 1))

        if new_index != self.__current_frame_index:
            self.load_frame(new_index)

    def prev_recording(self) -> None:
        """Navigate to the previous recording (sorted by date)."""
        if not self.__current_recording or not self.__all_recordings:
            return

        try:
            current_idx = self.__all_recordings.index(self.__current_recording)
        except ValueError:
            # Current recording not in list, refresh and try again
            self.__all_recordings = self.scan_all_recordings()
            try:
                current_idx = self.__all_recordings.index(self.__current_recording)
            except ValueError:
                return

        if current_idx <= 0:
            # Already at first recording
            return

        # Load previous recording
        self._load_recording(self.__all_recordings[current_idx - 1])

    def next_recording(self) -> None:
        """Navigate to the next recording (sorted by date)."""
        if not self.__current_recording or not self.__all_recordings:
            return

        try:
            current_idx = self.__all_recordings.index(self.__current_recording)
        except ValueError:
            # Current recording not in list, refresh and try again
            self.__all_recordings = self.scan_all_recordings()
            try:
                current_idx = self.__all_recordings.index(self.__current_recording)
            except ValueError:
                return

        if current_idx >= len(self.__all_recordings) - 1:
            # Already at last recording
            return

        # Load next recording
        self._load_recording(self.__all_recordings[current_idx + 1])

    def _load_recording(self, folder: Path) -> None:
        """Load a recording folder and show its first frame."""
        frames = self.scan_recording_frames(folder)
        if not frames:
            return

        self.__current_recording = folder.resolve()
        self.__frame_files = frames
        self.__current_frame_index = 0
        self.__frames_per_segment = self.calculate_frames_per_segment()

        # Load first frame
        self.load_frame(0)

    @handle_user_error
    def detect_bird(self) -> None:
        # Reset to original image first (clears any previous detection rectangles)
        self.__image_obj = tk.PhotoImage(file=self.__selected_image)
        self.set_image_preview()

        regions = [Region(*coords) for coords in self.__selection_regions] if self.__selection_regions else None
        self.__image_obj = tk.PhotoImage(
            data=get_annotated_image_bytes(self.detector, self.__selected_image, regions=regions),
            format="png",
        )
        self.set_image_preview()
        self.show_clear_button()

    def start_sync(self) -> None:
        """Start the sync operation in a background thread with progress dialog."""
        # Disable all buttons (freeze UI)
        self._set_buttons_enabled(False)

        # Create and show progress dialog
        self.__sync_dialog = SyncProgressDialog(self.root)

        # Start sync thread
        self.__sync_thread = threading.Thread(target=self._run_sync, daemon=True)
        self.__sync_thread.start()

        # Poll for completion
        self.root.after(100, self._check_sync_complete)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        """Enable or disable all action buttons."""
        state = "normal" if enabled else "disabled"
        self.sync_btn.config(state=state)
        self.select_btn.config(state=state)
        if self.detect_btn.winfo_ismapped():
            self.detect_btn.config(state=state)
        if self.clear_btn.winfo_ismapped():
            self.clear_btn.config(state=state)

    def _run_sync(self) -> None:
        """Run sync and conversion in background thread."""
        dialog = self.__sync_dialog

        try:
            with SyncManager() as sync:
                # Check if cancelled before starting
                if dialog.cancelled:
                    return

                # Sync files from remote
                synced_folders, total_files = sync.sync_all(
                    on_download_progress=lambda c, t, f: (
                        dialog.update_download_progress(c, t, f) if not dialog.cancelled else None
                    ),
                )

                if dialog.cancelled:
                    return

                if total_files == 0:
                    dialog.set_no_files_to_sync()
                else:
                    dialog.set_download_complete(total_files)

                # Convert downloaded playlists to images
                if not dialog.cancelled:
                    playlists_converted, frames = convert_all_playlists(
                        on_playlist_progress=lambda c, t, n: (
                            dialog.update_convert_progress(c, t, n) if not dialog.cancelled else None
                        ),
                    )

        except SyncError as e:
            dialog.set_error(str(e))
        except Exception as e:
            dialog.set_error(f"Unexpected error: {e}")

    def _check_sync_complete(self) -> None:
        """Poll for sync thread completion and cleanup."""
        if self.__sync_thread.is_alive():
            # Still running, check again later
            self.root.after(100, self._check_sync_complete)
            return

        # Thread finished, cleanup
        dialog = self.__sync_dialog
        error = dialog.get_error()
        dialog.close()

        # Re-enable buttons
        self._set_buttons_enabled(True)

        # Show error or success message
        if error:
            messagebox.showerror("Sync Error", error)
        elif not dialog.cancelled:
            messagebox.showinfo("Sync Complete", "Files synced and converted successfully.")

    def run(self) -> None:
        self.root.mainloop()
