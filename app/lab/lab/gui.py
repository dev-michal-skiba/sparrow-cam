import functools
import json
import re
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from processor.bird_detector import DEFAULT_DETECTION_PARAMS, BirdDetector

from lab import annotations, fine_tune
from lab.constants import ARCHIVE_DIR, FINE_TUNED_MODELS_DIR, IMAGE_FILENAME_PATTERN, IMAGES_DIR, PRESETS_DIR
from lab.converter import convert_playlist_to_pngs
from lab.exception import UserFacingError
from lab.sync import SyncError, SyncManager, remove_hls_files, remove_recording, remove_recording_locally
from lab.utils import Region, get_annotated_image_bytes

MIN_SELECTION_SIZE = 100
MIN_ANNOTATION_SIZE = 10


def get_ordinal_suffix(day: int) -> str:
    """Get the ordinal suffix for a day number (e.g., 1st, 2nd, 3rd, 4th)."""
    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def parse_recording_folder_name(folder_name: str) -> tuple[str | None, str | None]:
    """
    Parse recording folder name to extract datetime and key.

    Recording folder format: [{prefix}_]{ISO-timestamp}_{uuid}
    Examples:
        auto_2026-01-15T064557Z_5d83d036-3f12-4d9b-82f5-4d7eb1ab0d92
        2026-01-15T064557Z_5d83d036-3f12-4d9b-82f5-4d7eb1ab0d92

    Returns:
        Tuple of (datetime_str, key) where datetime_str is a human-readable format
        in local timezone and key is the prefix (e.g., "manual", "auto") or None if no prefix.

    Note: If timezone is not properly configured (e.g., WSL defaults to UTC),
    the datetime will still be in UTC. Configure WSL timezone with:
        sudo dpkg-reconfigure tzdata
    """

    # Pattern: optional prefix, underscore, ISO-timestamp, underscore, uuid
    pattern = (
        r"^(?:(\w+)_)?(\d{4}-\d{2}-\d{2}T\d{6}Z)_" r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"
    )
    match = re.match(pattern, folder_name, re.IGNORECASE)

    if not match:
        return None, None

    key = match.group(1)
    iso_timestamp = match.group(2)

    # Parse ISO timestamp (UTC) and convert to local timezone
    try:
        # Re-insert colons for fromisoformat: "2026-01-15T064557Z" -> "2026-01-15T06:45:57Z"
        iso_for_parse = f"{iso_timestamp[:13]}:{iso_timestamp[13:15]}:{iso_timestamp[15:]}"
        # Parse as UTC
        dt_utc = datetime.fromisoformat(iso_for_parse.replace("Z", "+00:00"))

        # Try to convert to local timezone
        # Note: In WSL with UTC timezone, astimezone() will return UTC
        # Set TZ environment variable or configure WSL timezone to fix this
        dt_local = dt_utc.astimezone()

        # Format as "1st January 2026 06:51:01 CET" (human-readable with ordinal day)
        day_ordinal = get_ordinal_suffix(dt_local.day)
        month_name = dt_local.strftime("%B")  # Full month name
        year = dt_local.year
        time_str = dt_local.strftime("%H:%M:%S")
        tz_name = dt_local.strftime("%Z")  # Timezone abbreviation (e.g., CET, GMT)

        datetime_str = f"{day_ordinal} {month_name} {year} {time_str} {tz_name}"
        return datetime_str, key
    except ValueError:
        return None, None


class SyncProgressDialog:
    """Modal dialog showing sync progress for per-stream pipeline (download, convert, cleanup)."""

    def __init__(self, parent: tk.Tk) -> None:
        self.parent = parent
        self.cancelled = False
        self._sync_error: str | None = None

        # Create modal dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Syncing Streams")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Make dialog non-resizable and centered
        self.dialog.resizable(False, False)
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        # Content frame with padding
        content = tk.Frame(self.dialog, padx=20, pady=20)
        content.pack(fill="both", expand=True)

        # Stream progress section (overall)
        self.stream_label = tk.Label(content, text="Preparing...", anchor="w")
        self.stream_label.pack(fill="x", pady=(0, 5))

        self.stream_progress = ttk.Progressbar(content, length=400, mode="determinate")
        self.stream_progress.pack(fill="x", pady=(0, 15))

        # Operation progress section (current operation within stream)
        self.operation_label = tk.Label(content, text="", anchor="w")
        self.operation_label.pack(fill="x", pady=(0, 5))

        self.operation_progress = ttk.Progressbar(content, length=400, mode="determinate")
        self.operation_progress.pack(fill="x", pady=(0, 15))

        # Status label (shows current filename or detail)
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
        self.status_label.config(text="Cancelling after current stream completes...")

    def _on_close(self) -> None:
        """Handle window close button - same as cancel."""
        self._on_cancel()

    def update_stream_progress(self, current: int, total: int, stream_name: str) -> None:
        """Update overall stream progress (thread-safe via parent.after)."""
        self.parent.after(0, self._do_update_stream, current, total, stream_name)

    def _do_update_stream(self, current: int, total: int, stream_name: str) -> None:
        if self.dialog.winfo_exists():
            self.stream_label.config(text=f"Stream {current}/{total}: {stream_name}")
            self.stream_progress["maximum"] = total
            self.stream_progress["value"] = current

    def update_operation_progress(self, current: int, total: int, operation: str, detail: str = "") -> None:
        """Update current operation progress (thread-safe via parent.after)."""
        self.parent.after(0, self._do_update_operation, current, total, operation, detail)

    def _do_update_operation(self, current: int, total: int, operation: str, detail: str) -> None:
        if self.dialog.winfo_exists():
            self.operation_label.config(text=f"{operation}: {current}/{total}")
            self.operation_progress["maximum"] = total
            self.operation_progress["value"] = current
            if detail:
                self.status_label.config(text=detail)

    def set_operation_status(self, status: str) -> None:
        """Set operation status message (thread-safe via parent.after)."""
        self.parent.after(0, self._do_set_operation_status, status)

    def _do_set_operation_status(self, status: str) -> None:
        if self.dialog.winfo_exists():
            self.status_label.config(text=status)

    def set_no_streams_to_sync(self) -> None:
        """Show message when no streams need syncing."""
        self.parent.after(0, self._do_set_no_streams)

    def _do_set_no_streams(self) -> None:
        if self.dialog.winfo_exists():
            self.stream_label.config(text="No new streams to sync")
            self.stream_progress["value"] = 0
            self.operation_label.config(text="")
            self.operation_progress["value"] = 0
            self.status_label.config(text="All streams are up to date")

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


class FineTuneDialog:
    """Modal dialog for collecting fine-tune parameters (version, description, preset)."""

    def __init__(self, parent: tk.Tk) -> None:
        self.parent = parent
        self.result: tuple[str, str, Path | None] | None = None  # (version, description, preset_path)

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Fine Tune Model")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.resizable(False, False)
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)

        content = tk.Frame(self.dialog, padx=20, pady=20)
        content.pack(fill="both", expand=True)

        # Version
        tk.Label(content, text="Version:", anchor="w").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self._version_var = tk.StringVar()
        version_entry = tk.Entry(content, textvariable=self._version_var, width=20)
        version_entry.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=(0, 4))
        tk.Label(content, text="Format: v1.2.3", fg="#888888", font=("TkDefaultFont", 8)).grid(
            row=1, column=1, sticky="w", padx=(8, 0), pady=(0, 12)
        )

        # Description
        tk.Label(content, text="Description:", anchor="w").grid(row=2, column=0, sticky="nw", pady=(0, 4))
        self._desc_text = tk.Text(content, width=40, height=5, wrap="word")
        self._desc_text.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(0, 4))
        self._desc_char_label = tk.Label(content, text="0 / 256", fg="#888888", font=("TkDefaultFont", 8))
        self._desc_char_label.grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(0, 12))
        self._desc_text.bind("<KeyRelease>", self._on_desc_changed)

        # Preset
        tk.Label(content, text="Preset:", anchor="w").grid(row=4, column=0, sticky="w", pady=(0, 4))
        preset_options = ["(None)"]
        if PRESETS_DIR.exists():
            preset_options += sorted(f.name for f in PRESETS_DIR.glob("*.json"))
        self._preset_var = tk.StringVar(value="(None)")
        preset_combo = ttk.Combobox(
            content, textvariable=self._preset_var, values=preset_options, state="readonly", width=22
        )
        preset_combo.grid(row=4, column=1, sticky="w", padx=(8, 0), pady=(0, 20))

        # Buttons
        btn_frame = tk.Frame(content)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=(0, 0))
        tk.Button(btn_frame, text="Start", command=self._on_start, width=10).pack(side="left", padx=(0, 8))
        tk.Button(btn_frame, text="Cancel", command=self._on_cancel, width=10).pack(side="left")

        self._center_dialog()
        version_entry.focus_set()

    def _center_dialog(self) -> None:
        self.dialog.update_idletasks()
        px, py = self.parent.winfo_x(), self.parent.winfo_y()
        pw, ph = self.parent.winfo_width(), self.parent.winfo_height()
        dw, dh = self.dialog.winfo_width(), self.dialog.winfo_height()
        self.dialog.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 2}")

    def _on_desc_changed(self, _event=None) -> None:
        count = len(self._desc_text.get("1.0", "end-1c"))
        self._desc_char_label.config(text=f"{count} / 256")

    def _on_start(self) -> None:
        version = self._version_var.get().strip()
        if not fine_tune.validate_version(version):
            messagebox.showerror(
                "Invalid Version",
                "Version must match format v<major>.<minor>.<patch> (e.g. v1.0.0).",
                parent=self.dialog,
            )
            return

        description = self._desc_text.get("1.0", "end-1c")
        if len(description) > 256:
            messagebox.showerror(
                "Description Too Long",
                f"Description must be at most 256 characters (currently {len(description)}).",
                parent=self.dialog,
            )
            return

        output_dir = FINE_TUNED_MODELS_DIR / version
        if output_dir.exists():
            messagebox.showerror(
                "Version Already Exists",
                f"A fine-tuned model for version '{version}' already exists.\n" "Choose a different version.",
                parent=self.dialog,
            )
            return

        preset_name = self._preset_var.get()
        preset_path: Path | None = None
        if preset_name != "(None)":
            preset_path = PRESETS_DIR / preset_name
            try:
                fine_tune.load_preset(preset_path)
            except (ValueError, OSError, KeyError) as exc:
                messagebox.showerror("Invalid Preset", str(exc), parent=self.dialog)
                return

        self.result = (version, description, preset_path)
        self.dialog.grab_release()
        self.dialog.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.dialog.grab_release()
        self.dialog.destroy()

    def wait(self) -> tuple[str, str, Path | None] | None:
        """Block until dialog is closed; return result or None if cancelled."""
        self.parent.wait_window(self.dialog)
        return self.result


class ModelSelectDialog:
    """Modal dialog for selecting a model for detection."""

    def __init__(self, parent: tk.Tk) -> None:
        self.parent = parent
        self.result: dict | None = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Model for Detection")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.resizable(False, False)
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)

        content = tk.Frame(self.dialog, padx=20, pady=20)
        content.pack(fill="both", expand=True)

        tk.Label(content, text="Available Models:", anchor="w").pack(fill="x", pady=(0, 8))

        # Listbox with scrollbar for model selection
        list_frame = tk.Frame(content)
        list_frame.pack(fill="both", expand=True, pady=(0, 12))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self._listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, width=60, height=8)
        self._listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._listbox.yview)

        # Get available models and populate listbox
        self._models = fine_tune.get_available_models()
        for model in self._models:
            if model["is_base"]:
                display_text = "yolov8n.pt (Base model)"
            else:
                display_text = f"{model['version']} - {model['description']}"
            self._listbox.insert(tk.END, display_text)

        # Select the first model by default (newest fine-tuned or base if none exist)
        if self._models:
            self._listbox.selection_set(0)

        # Details frame
        details_frame = tk.Frame(content)
        details_frame.pack(fill="x", pady=(0, 12))

        tk.Label(details_frame, text="Base model:", font=("TkDefaultFont", 8)).grid(
            row=0, column=0, sticky="w", pady=(0, 2)
        )
        self._base_model_label = tk.Label(details_frame, text="", fg="#666666", font=("TkDefaultFont", 8))
        self._base_model_label.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=(0, 2))

        tk.Label(details_frame, text="Classes:", font=("TkDefaultFont", 8)).grid(
            row=1, column=0, sticky="nw", pady=(0, 2)
        )
        self._classes_label = tk.Label(
            details_frame, text="", fg="#666666", font=("TkDefaultFont", 8), justify="left", wraplength=300
        )
        self._classes_label.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(0, 2))

        # Update details when selection changes
        self._listbox.bind("<<ListboxSelect>>", self._on_selection_changed)
        self._on_selection_changed()

        # Buttons
        btn_frame = tk.Frame(content)
        btn_frame.pack()
        tk.Button(btn_frame, text="Select", command=self._on_select, width=10).pack(side="left", padx=(0, 8))
        tk.Button(btn_frame, text="Cancel", command=self._on_cancel, width=10).pack(side="left")

        self._center_dialog()

    def _center_dialog(self) -> None:
        self.dialog.update_idletasks()
        px, py = self.parent.winfo_x(), self.parent.winfo_y()
        pw, ph = self.parent.winfo_width(), self.parent.winfo_height()
        dw, dh = self.dialog.winfo_width(), self.dialog.winfo_height()
        self.dialog.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 2}")

    def _on_selection_changed(self, _event=None) -> None:
        """Update details label when selection changes."""
        selection = self._listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        model = self._models[idx]

        self._base_model_label.config(text=model["base_model"])

        if model["classes"] is None:
            classes_text = "Bird class only (default)"
        else:
            classes_list = ", ".join(sorted(model["classes"].values()))
            classes_text = classes_list

        self._classes_label.config(text=classes_text)

    def _on_select(self) -> None:
        selection = self._listbox.curselection()
        if selection:
            self.result = self._models[selection[0]]
        self.dialog.grab_release()
        self.dialog.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.dialog.grab_release()
        self.dialog.destroy()

    def wait(self) -> dict | None:
        """Block until dialog is closed; return selected model dict or None if cancelled."""
        self.parent.wait_window(self.dialog)
        return self.result


class RemoveRecordingDialog:
    """Modal dialog for choosing how to remove a recording: locally or completely."""

    def __init__(self, parent: tk.Tk, recording_name: str) -> None:
        self.parent = parent
        self.result: str | None = None  # "local", "complete", or None (cancelled)

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Remove Recording")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.resizable(False, False)
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)

        content = tk.Frame(self.dialog, padx=20, pady=20)
        content.pack(fill="both", expand=True)

        tk.Label(content, text=f"Recording: {recording_name}", anchor="w", font=("TkDefaultFont", 9, "bold")).pack(
            fill="x", pady=(0, 16)
        )

        tk.Label(content, text="Remove locally", anchor="w", font=("TkDefaultFont", 10, "bold")).pack(fill="x")
        tk.Label(
            content,
            text="Deletes local frames only. Archive folder is kept so it won't re-sync from server.",
            anchor="w",
            wraplength=360,
            justify="left",
        ).pack(fill="x", pady=(2, 12))

        tk.Label(content, text="Remove completely", anchor="w", font=("TkDefaultFont", 10, "bold")).pack(fill="x")
        tk.Label(
            content,
            text="Deletes local frames, local archive, and server copy. Cannot be undone.",
            anchor="w",
            wraplength=360,
            justify="left",
        ).pack(fill="x", pady=(2, 20))

        btn_frame = tk.Frame(content)
        btn_frame.pack()
        tk.Button(btn_frame, text="Cancel", command=self._on_cancel, width=12).pack(side="left", padx=(0, 8))
        tk.Button(btn_frame, text="Remove locally", command=self._on_local, width=14).pack(side="left", padx=(0, 8))
        tk.Button(btn_frame, text="Remove completely", command=self._on_complete, width=16, fg="red").pack(side="left")

        self._center_dialog()

    def _center_dialog(self) -> None:
        self.dialog.update_idletasks()
        px, py = self.parent.winfo_x(), self.parent.winfo_y()
        pw, ph = self.parent.winfo_width(), self.parent.winfo_height()
        dw, dh = self.dialog.winfo_width(), self.dialog.winfo_height()
        self.dialog.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 2}")

    def _on_cancel(self) -> None:
        self.result = None
        self.dialog.grab_release()
        self.dialog.destroy()

    def _on_local(self) -> None:
        self.result = "local"
        self.dialog.grab_release()
        self.dialog.destroy()

    def _on_complete(self) -> None:
        self.result = "complete"
        self.dialog.grab_release()
        self.dialog.destroy()

    def wait(self) -> str | None:
        """Block until dialog is closed; return 'local', 'complete', or None (cancelled)."""
        self.parent.wait_window(self.dialog)
        return self.result


class LabGUI:
    """Tkinter GUI for selecting PNGs in a storage directory and running detection."""

    def __init__(self) -> None:
        # Initialize detector with default settings
        self.__selected_model_info: dict | None = None
        self._init_detector()

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

        # Annotation mode state
        self.__annotation_mode: bool = False
        self.__annotation_items: list[dict] = []  # [{class_id, x1, y1, x2, y2}]
        self.__annotation_row_widgets: list[tk.Frame] = []  # row frames in annotation list
        self.__last_selected_class: str = annotations.AVAILABLE_CLASSES[0][0]

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

        self.fine_tune_btn = tk.Button(self.button_frame, text="Fine tune", command=self.open_fine_tune_dialog)
        self.fine_tune_btn.pack(side="left", padx=(0, 8))

        self.select_model_btn = tk.Button(self.button_frame, text="Select model", command=self.open_model_select_dialog)
        self.select_model_btn.pack(side="left", padx=(0, 8))

        self.remove_btn = tk.Button(self.button_frame, text="Remove", command=self.start_remove_recording)

        self.detect_btn = tk.Button(self.button_frame, text="Detect Bird", command=self.detect_bird)

        self.clear_btn = tk.Button(self.button_frame, text="Clear", command=self.clear_all)

        self.annotate_btn = tk.Button(self.button_frame, text="Annotate", command=self.enter_annotation_mode)

        self.submit_btn = tk.Button(self.button_frame, text="Submit Annotations", command=self.submit_annotations)

        self.leave_annotation_btn = tk.Button(
            self.button_frame, text="Leave annotation mode", command=self.leave_annotation_mode
        )

        self.remove_annotation_btn = tk.Button(
            self.button_frame, text="Remove annotation", command=self.remove_frame_annotation
        )

        # Detection parameters frame (always visible)
        self.params_frame = tk.Frame(self.root)
        self.params_frame.pack(pady=(0, 12))

        self.conf_label = tk.Label(self.params_frame, text="Confidence:")
        self.conf_label.pack(side="left", padx=(0, 4))

        self.conf_var = tk.DoubleVar(value=DEFAULT_DETECTION_PARAMS["conf"])
        self.conf_spinbox = ttk.Spinbox(
            self.params_frame,
            from_=0.0,
            to=1.0,
            increment=0.01,
            textvariable=self.conf_var,
            width=6,
            format="%.2f",
        )
        self.conf_spinbox.pack(side="left", padx=(0, 16))

        self.imgsz_label = tk.Label(self.params_frame, text="Image Size:")
        self.imgsz_label.pack(side="left", padx=(0, 4))

        self.imgsz_var = tk.IntVar(value=DEFAULT_DETECTION_PARAMS["imgsz"])
        self.imgsz_spinbox = ttk.Spinbox(
            self.params_frame,
            from_=1,
            to=9999,
            increment=1,
            textvariable=self.imgsz_var,
            width=6,
        )
        self.imgsz_spinbox.pack(side="left", padx=(0, 16))

        self.iou_label = tk.Label(self.params_frame, text="IOU:")
        self.iou_label.pack(side="left", padx=(0, 4))

        self.iou_var = tk.DoubleVar(value=DEFAULT_DETECTION_PARAMS["iou"])
        self.iou_spinbox = ttk.Spinbox(
            self.params_frame,
            from_=0.0,
            to=1.0,
            increment=0.01,
            textvariable=self.iou_var,
            width=6,
            format="%.2f",
        )
        self.iou_spinbox.pack(side="left", padx=(0, 16))

        self.export_btn = tk.Button(self.params_frame, text="Export", command=self.export_settings)
        self.export_btn.pack(side="left", padx=(0, 4))

        self.import_btn = tk.Button(self.params_frame, text="Import", command=self.import_settings)
        self.import_btn.pack(side="left")

        # Recording info header (hidden until recording is loaded)
        self.__recording_info_text = tk.StringVar(value="")
        self.recording_info_label = tk.Label(
            self.root,
            textvariable=self.__recording_info_text,
            font=("Helvetica", 14, "bold"),
            fg="#000000",
        )

        # Annotation status label (hidden until recording is loaded)
        # Use Text widget to support colored status text
        self.annotation_status_label = tk.Text(
            self.root,
            height=1,
            font=("Helvetica", 14, "bold"),
            wrap="word",
            state="disabled",
            borderwidth=0,
            highlightthickness=0,
            bg=self.root.cget("bg"),
        )
        # Configure center tag for centering text
        self.annotation_status_label.tag_configure("center", justify="center")

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

        # Annotation list (shown only in annotation mode, below the canvas)
        self.annotation_list_frame = tk.Frame(self.root)

        self.path_hint = tk.Label(
            self.root,
            textvariable=self.__selected_image_text,
            justify="left",
            fg="#555555",
            font=("TkDefaultFont", 9),
            anchor="w",
        )
        self.path_hint.pack(side="bottom", fill="x", padx=self.content_pad, pady=(0, 12))

        # Global annotation stats frame (top-left corner, always visible)
        self.stats_frame = tk.Frame(self.root, bg="white")
        self.stats_frame.place(relx=0.0, rely=0.0, anchor="nw", x=self.content_pad, y=self.content_pad)

        # Stats text (selectable/copyable with Text widget)
        self.stats_text = tk.Text(
            self.stats_frame,
            fg="#000000",
            bg="white",
            font=("Helvetica", 12),
            height=12,
            width=40,
            relief="flat",
            borderwidth=0,
            wrap="word",
        )
        self.stats_text.pack(anchor="w", fill="both", expand=True)
        self.stats_text.config(state="disabled")  # Read-only but still selectable

        # Update stats on initialization
        self.root.after(100, self._update_stats_display)

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

    def show_annotation_status(self) -> None:
        """Show annotation status label below recording info (above image canvas)."""
        if not self.annotation_status_label.winfo_ismapped():
            if self.recording_info_label.winfo_ismapped():
                self.annotation_status_label.pack(after=self.recording_info_label, pady=(0, 4))
            else:
                self.annotation_status_label.pack(before=self.image_canvas, pady=(0, 4))

    def hide_annotation_status(self) -> None:
        """Hide annotation status label."""
        if self.annotation_status_label.winfo_ismapped():
            self.annotation_status_label.pack_forget()

    def update_annotation_status(self) -> None:
        """Refresh the annotation status label for the current frame."""
        if self.__selected_image is None or self.__current_recording is None:
            self.hide_annotation_status()
            return
        status = annotations.get_annotation_status(self.__selected_image, self.__current_recording)

        # Map status to display text and color
        if status == "False":
            display_text = "None"
            color = "#FF8C00"  # Orange
        elif status == "True [positive]":
            display_text = "Annotated as Positive"
            color = "#22C55E"  # Green
        else:  # "True [negative]"
            display_text = "Annotated as Negative"
            color = "#22C55E"  # Green

        # Update Text widget with colored status
        self.annotation_status_label.config(state="normal")
        self.annotation_status_label.delete("1.0", "end")
        self.annotation_status_label.insert("1.0", f"Annotation status: {display_text}")

        # Apply center alignment to entire line
        self.annotation_status_label.tag_add("center", "1.0", "end")

        # Configure tag color
        tag_name = "orange" if color == "#FF8C00" else "green"
        self.annotation_status_label.tag_configure(tag_name, foreground=color)

        # Color only the status part (skip first letter)
        # "Annotation status: " is 19 chars, so start at char 20 (19 counting from 0) to skip first letter of status
        start_idx = "1.0 + 19c"
        end_idx = "end"
        self.annotation_status_label.tag_add(tag_name, start_idx, end_idx)

        self.annotation_status_label.config(state="disabled")
        self.show_annotation_status()

    def show_recording_info(self) -> None:
        """Show recording info header above the image preview."""
        if not self.recording_info_label.winfo_ismapped():
            # Pack before image_canvas to position it above the image preview
            self.recording_info_label.pack(before=self.image_canvas, pady=(12, 8))

    def hide_recording_info(self) -> None:
        """Hide recording info header."""
        if self.recording_info_label.winfo_ismapped():
            self.recording_info_label.pack_forget()

    def update_recording_info(self, folder: Path) -> None:
        """Update recording info header with extracted datetime and key."""
        folder_name = folder.name
        datetime_str, key = parse_recording_folder_name(folder_name)

        if datetime_str is not None:
            # Format the info display
            if key:
                info_text = f"{datetime_str} ({key})"
            else:
                info_text = f"{datetime_str}"
            self.__recording_info_text.set(info_text)
            self.show_recording_info()
        else:
            # Failed to parse, hide the label
            self.hide_recording_info()

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

    def show_annotate_button(self) -> None:
        if not self.annotate_btn.winfo_ismapped():
            self.annotate_btn.pack(side="left", padx=(8, 0))

    def hide_annotate_button(self) -> None:
        if self.annotate_btn.winfo_ismapped():
            self.annotate_btn.pack_forget()

    def show_submit_button(self) -> None:
        if not self.submit_btn.winfo_ismapped():
            self.submit_btn.pack(side="left", padx=(8, 0))

    def hide_submit_button(self) -> None:
        if self.submit_btn.winfo_ismapped():
            self.submit_btn.pack_forget()

    def show_leave_annotation_button(self) -> None:
        if not self.leave_annotation_btn.winfo_ismapped():
            self.leave_annotation_btn.pack(side="left", padx=(8, 0))

    def hide_leave_annotation_button(self) -> None:
        if self.leave_annotation_btn.winfo_ismapped():
            self.leave_annotation_btn.pack_forget()

    def show_remove_annotation_button(self) -> None:
        if not self.remove_annotation_btn.winfo_ismapped():
            self.remove_annotation_btn.pack(side="left", padx=(8, 0))

    def hide_remove_annotation_button(self) -> None:
        if self.remove_annotation_btn.winfo_ismapped():
            self.remove_annotation_btn.pack_forget()

    def show_detect_button(self) -> None:
        if not self.detect_btn.winfo_ismapped():
            self.detect_btn.pack(side="left")

    def show_remove_button(self) -> None:
        if not self.remove_btn.winfo_ismapped():
            self.remove_btn.pack(side="left", padx=(8, 0))

    def hide_remove_button(self) -> None:
        if self.remove_btn.winfo_ismapped():
            self.remove_btn.pack_forget()

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
        color = "green" if self.__annotation_mode else "blue"
        self.__current_rect = self.image_canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline=color, width=2
        )

    def on_selection_drag(self, event) -> None:
        """Update selection rectangle while dragging."""
        if self.__selection_start is None or self.__current_rect is None:
            return
        x1, y1 = self.__selection_start
        x2, y2 = event.x, event.y

        if not self.__annotation_mode:
            # Constrain to square: use the larger dimension for both
            dx = x2 - x1
            dy = y2 - y1
            side = max(abs(dx), abs(dy))
            x2 = x1 + side * (1 if dx >= 0 else -1)
            y2 = y1 + side * (1 if dy >= 0 else -1)

        self.image_canvas.coords(self.__current_rect, x1, y1, x2, y2)

        # Only show ROI dimension text for detection regions, not for annotation mode
        if self.__annotation_mode:
            return

        # Calculate normalized ROI coordinates
        roi_x1, roi_x2 = min(x1, x2), max(x1, x2)
        roi_y1, roi_y2 = min(y1, y2), max(y1, y2)
        # Position text at the top-left corner of the rectangle
        text_x = roi_x1 + 4
        text_y = roi_y1 + 4
        side = max(abs(x2 - x1), abs(y2 - y1))
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
        """Finalize selection rectangle and add to the list of regions."""
        if self.__selection_start is None or self.__image_obj is None:
            return

        x1, y1 = self.__selection_start
        x2, y2 = event.x, event.y

        if not self.__annotation_mode:
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
        img_width = self.__image_obj.width()
        img_height = self.__image_obj.height()
        x1 = max(0, min(x1, img_width))
        x2 = max(0, min(x2, img_width))
        y1 = max(0, min(y1, img_height))
        y2 = max(0, min(y2, img_height))

        actual_w = x2 - x1
        actual_h = y2 - y1

        if self.__annotation_mode:
            min_size = MIN_ANNOTATION_SIZE
            too_small = actual_w < min_size or actual_h < min_size
            size_label = f"{actual_w}x{actual_h}px"
            error_msg = (
                f"Annotation must be at least {min_size}x{min_size} pixels.\n"
                f"Your selection: {actual_w}x{actual_h} pixels."
            )
        else:
            actual_side = x2 - x1
            min_size = MIN_SELECTION_SIZE
            too_small = actual_side < min_size
            size_label = f"{actual_side}px"
            error_msg = (
                f"Selection must be at least {min_size}x{min_size} pixels.\n"
                f"Your selection: {actual_side}x{actual_side} pixels."
            )

        if not too_small:
            if self.__annotation_mode:
                # Add annotation item and UI row (no ROI labels shown for annotations)
                class_id = next(
                    (cid for name, cid in annotations.AVAILABLE_CLASSES if name == self.__last_selected_class),
                    annotations.AVAILABLE_CLASSES[0][1],
                )
                self.__annotation_items.append({"class_id": class_id, "x1": x1, "y1": y1, "x2": x2, "y2": y2})
                self.__selection_rects.append(self.__current_rect)
                self.__current_rect = None
                self.hide_dimension_text()
                idx = len(self.__annotation_items) - 1
                self._add_annotation_row(idx)
            else:
                self.__selection_regions.append((x1, y1, x2, y2))
                self.__selection_rects.append(self.__current_rect)
                self.__current_rect = None
                if self.__dimension_text is not None:
                    roi_str = f"ROI: ({x1}, {y1}, {x2}, {y2})\nSize: {size_label}"
                    self.image_canvas.itemconfig(self.__dimension_text, text=roi_str)
                    self.image_canvas.coords(self.__dimension_text, x1 + 4, y1 + 4)
                    bbox = self.image_canvas.bbox(self.__dimension_text)
                    if bbox and self.__dimension_bg is not None:
                        self.image_canvas.coords(
                            self.__dimension_bg, bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2
                        )
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
            messagebox.showerror("Selection too small", error_msg)

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

        # Update recording info header
        self.update_recording_info(folder)

        # Load first frame
        self.load_frame(0)

        # Show navigation controls
        self.show_navigation()
        self.show_detect_button()
        self.show_remove_button()
        self.show_annotate_button()

    def load_frame(self, index: int) -> None:
        """
        Load a frame at the specified index.

        Clamps index to valid range, preserves selection regions (except in annotation mode).
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

        # Clear canvas elements
        self.clear_canvas_elements()
        self.set_image_preview()

        if self.__annotation_mode:
            # In annotation mode: clear annotations and reload from disk for new frame
            self.__annotation_items.clear()
            self._clear_annotation_list_ui()
            self._load_frame_annotations()
        else:
            # Redraw selections on the new image (detection ROIs)
            self.redraw_selections()

        # Update progress display
        self.update_progress_display()

        # Update annotation status label
        self.update_annotation_status()

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

        # Update recording info header
        self.update_recording_info(folder)

        # Load first frame
        self.load_frame(0)

        # Ensure remove button is shown; annotate only when not in annotation mode
        self.show_remove_button()
        if not self.__annotation_mode:
            self.show_annotate_button()

    @handle_user_error
    def detect_bird(self) -> None:
        # Reset to original image first (clears any previous detection rectangles)
        self.__image_obj = tk.PhotoImage(file=self.__selected_image)
        self.set_image_preview()

        regions = [Region(*coords) for coords in self.__selection_regions] if self.__selection_regions else None
        self.__image_obj = tk.PhotoImage(
            data=get_annotated_image_bytes(
                self.detector,
                self.__selected_image,
                regions=regions,
                conf=self.conf_var.get(),
                imgsz=self.imgsz_var.get(),
                iou=self.iou_var.get(),
            ),
            format="png",
        )
        self.set_image_preview()
        self.show_clear_button()

    def export_settings(self) -> None:
        """Export detection parameters and regions to a JSON file."""
        PRESETS_DIR.mkdir(parents=True, exist_ok=True)

        file_path = filedialog.asksaveasfilename(
            initialdir=str(PRESETS_DIR),
            title="Export Settings",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not file_path:
            return

        settings = {
            "params": {
                "conf": self.conf_var.get(),
                "imgsz": self.imgsz_var.get(),
                "iou": self.iou_var.get(),
            },
            "regions": [list(region) for region in self.__selection_regions],
        }

        with open(file_path, "w") as f:
            json.dump(settings, f, indent=2)

        messagebox.showinfo("Export Complete", f"Settings exported to:\n{file_path}")

    def import_settings(self) -> None:
        """Import detection parameters and regions from a JSON file."""
        initial_dir = str(PRESETS_DIR) if PRESETS_DIR.exists() else str(PRESETS_DIR.parent)

        file_path = filedialog.askopenfilename(
            initialdir=initial_dir,
            title="Import Settings",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not file_path:
            return

        try:
            with open(file_path) as f:
                settings = json.load(f)

            # Update detection parameters
            if "params" in settings:
                params = settings["params"]
                if "conf" in params:
                    self.conf_var.set(params["conf"])
                if "imgsz" in params:
                    self.imgsz_var.set(params["imgsz"])
                if "iou" in params:
                    self.iou_var.set(params["iou"])

            # Update regions
            if "regions" in settings:
                # Clear existing regions and canvas elements
                self.clear_canvas_elements()
                self.__selection_regions.clear()

                # Load new regions
                for region in settings["regions"]:
                    if len(region) == 4:
                        self.__selection_regions.append(tuple(region))

                # Redraw selections if image is loaded
                if self.__image_obj is not None:
                    self.redraw_selections()

            messagebox.showinfo("Import Complete", f"Settings imported from:\n{file_path}")

        except (json.JSONDecodeError, OSError) as e:
            messagebox.showerror("Import Error", f"Failed to import settings:\n{e}")

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
        self.fine_tune_btn.config(state=state)
        if self.detect_btn.winfo_ismapped():
            self.detect_btn.config(state=state)
        if self.clear_btn.winfo_ismapped():
            self.clear_btn.config(state=state)
        if self.remove_btn.winfo_ismapped():
            self.remove_btn.config(state=state)
        if self.annotate_btn.winfo_ismapped():
            self.annotate_btn.config(state=state)
        self.conf_spinbox.config(state=state)
        self.imgsz_spinbox.config(state=state)
        self.iou_spinbox.config(state=state)
        self.export_btn.config(state=state)
        self.import_btn.config(state=state)
        for btn in (
            self.prev_rec_btn,
            self.next_rec_btn,
            self.nav_minus_5s_btn,
            self.nav_minus_1s_btn,
            self.nav_minus_5f_btn,
            self.nav_minus_1f_btn,
            self.nav_plus_1f_btn,
            self.nav_plus_5f_btn,
            self.nav_plus_1s_btn,
            self.nav_plus_5s_btn,
        ):
            btn.config(state=state)
        self.progress_bar.config(state=state)

    def _set_navigation_buttons_enabled(self, enabled: bool) -> None:
        """Enable or disable navigation buttons specifically."""
        state = "normal" if enabled else "disabled"
        for btn in (
            self.prev_rec_btn,
            self.next_rec_btn,
            self.nav_minus_5s_btn,
            self.nav_minus_1s_btn,
            self.nav_minus_5f_btn,
            self.nav_minus_1f_btn,
            self.nav_plus_1f_btn,
            self.nav_plus_5f_btn,
            self.nav_plus_1s_btn,
            self.nav_plus_5s_btn,
        ):
            btn.config(state=state)

    def _run_sync(self) -> None:
        """Run sync, conversion, and cleanup in background thread (per-stream pipeline)."""
        dialog = self.__sync_dialog

        try:
            with SyncManager() as sync:
                # Check if cancelled before starting
                if dialog.cancelled:
                    return

                # Get list of streams to process
                missing_folders = sync.get_missing_folders()

                if not missing_folders:
                    dialog.set_no_streams_to_sync()
                    return

                total_streams = len(missing_folders)

                # Process each stream: download -> convert -> cleanup
                # Note: Each stream is processed atomically - once started, it will complete
                # all three steps before checking for cancellation
                for idx, folder in enumerate(missing_folders):
                    # Check for cancellation only at the start of each stream
                    # This ensures each stream is fully processed (downloaded, converted, cleaned)
                    if dialog.cancelled:
                        return

                    stream_num = idx + 1
                    stream_name = folder.split("/")[-1]  # Get folder name from path

                    # Update stream progress
                    dialog.update_stream_progress(stream_num, total_streams, stream_name)

                    # Step 1: Download stream
                    dialog.set_operation_status(f"Downloading stream {stream_num}/{total_streams}...")
                    sync.sync_single_folder(
                        folder,
                        on_file_progress=lambda c, t, f: (
                            dialog.update_operation_progress(c, t, "Downloading", f) if not dialog.cancelled else None
                        ),
                    )

                    # Step 2: Convert stream
                    dialog.set_operation_status(f"Converting stream {stream_num}/{total_streams}...")
                    folder_path = ARCHIVE_DIR / folder

                    # Convert with progress tracking
                    convert_playlist_to_pngs(
                        folder_path,
                        on_file_progress=lambda c, t, f: (
                            dialog.update_operation_progress(c, t, "Converting", f) if not dialog.cancelled else None
                        ),
                    )

                    # Step 3: Cleanup HLS files
                    dialog.set_operation_status(f"Cleaning up stream {stream_num}/{total_streams}...")
                    remove_hls_files(folder)

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

    def _get_recording_relative_path(self) -> str | None:
        """
        Get the relative path of the current recording from IMAGES_DIR.

        Returns the path in format: {year}/{month}/{day}/{folder_name}
        or None if no recording is selected.
        """
        if self.__current_recording is None:
            return None

        try:
            return str(self.__current_recording.relative_to(IMAGES_DIR))
        except ValueError:
            return None

    def start_remove_recording(self) -> None:
        """Start the remove recording operation after user confirmation."""
        if self.__current_recording is None:
            messagebox.showerror("No Recording", "No recording is currently selected.")
            return

        relative_path = self._get_recording_relative_path()
        if relative_path is None:
            messagebox.showerror("Error", "Cannot determine recording path.")
            return

        # Show choice dialog
        dialog = RemoveRecordingDialog(self.root, self.__current_recording.name)
        mode = dialog.wait()

        if mode is None:
            return

        # Store the relative path and mode for the background thread
        self.__remove_relative_path = relative_path
        self.__remove_mode = mode

        # Disable all buttons (freeze UI)
        self._set_buttons_enabled(False)

        # Start removal thread
        self.__remove_thread = threading.Thread(target=self._run_remove, daemon=True)
        self.__remove_error: str | None = None
        self.__remove_thread.start()

        # Poll for completion
        self.root.after(100, self._check_remove_complete)

    def _run_remove(self) -> None:
        """Run removal operation in background thread."""
        try:
            if self.__remove_mode == "local":
                remove_recording_locally(self.__remove_relative_path)
            else:
                remove_recording(self.__remove_relative_path)
        except SyncError as e:
            self.__remove_error = str(e)
        except Exception as e:
            self.__remove_error = f"Unexpected error: {e}"

    def _check_remove_complete(self) -> None:
        """Poll for removal thread completion and cleanup."""
        if self.__remove_thread.is_alive():
            # Still running, check again later
            self.root.after(100, self._check_remove_complete)
            return

        # Thread finished
        error = self.__remove_error

        # Re-enable buttons
        self._set_buttons_enabled(True)

        if error:
            messagebox.showerror("Removal Error", error)
        else:
            # Removal succeeded - try to load previous recording
            self._load_previous_after_removal()
            messagebox.showinfo("Removal Complete", "Recording removed successfully.")

    def _load_previous_after_removal(self) -> None:
        """Load the previous recording after current one is removed."""
        # Find the index of the removed recording in the old list
        removed_recording = self.__current_recording
        prev_recording_to_load: Path | None = None

        if removed_recording and self.__all_recordings:
            try:
                removed_idx = self.__all_recordings.index(removed_recording)
                if removed_idx > 0:
                    # There's a previous recording - remember it
                    prev_recording_to_load = self.__all_recordings[removed_idx - 1]
            except ValueError:
                pass

        # Refresh recordings list (the removed one should no longer be there)
        self.__all_recordings = self.scan_all_recordings()

        # Try to load the previous recording
        if prev_recording_to_load and prev_recording_to_load in self.__all_recordings:
            self._load_recording(prev_recording_to_load)
        else:
            # No previous recording available - reset to empty state
            self._reset_recording_state()

    def _reset_recording_state(self) -> None:
        """Reset UI state when no recording is available to display."""
        # Clear recording state
        self.__current_recording = None
        self.__frame_files = []
        self.__current_frame_index = 0
        self.__frames_per_segment = 0

        # Clear image and canvas
        self.__selected_image = None
        self.__selected_image_text.set("No file selected")
        if self.__canvas_image_id is not None:
            self.image_canvas.delete(self.__canvas_image_id)
            self.__canvas_image_id = None
        self.__image_obj = None

        # Clear selections
        self.clear_all()

        # Reset annotation mode state
        self.__annotation_mode = False
        self.__annotation_items.clear()
        self._clear_annotation_list_ui()

        # Hide navigation, recording info, annotation status and buttons
        self.hide_navigation()
        self.hide_recording_info()
        self.hide_annotation_status()
        self.hide_remove_button()
        self.hide_annotate_button()
        self.hide_submit_button()
        self.hide_leave_annotation_button()
        self.hide_remove_annotation_button()

        # Hide detect button (it's shown when recording is loaded)
        if self.detect_btn.winfo_ismapped():
            self.detect_btn.pack_forget()

    # ------------------------------------------------------------------
    # Annotation list UI helpers
    # ------------------------------------------------------------------

    def _add_annotation_row(self, idx: int) -> None:
        """Add a row for annotation item at index idx to the annotation list frame."""
        item = self.__annotation_items[idx]
        row = tk.Frame(self.annotation_list_frame)
        row.pack(fill="x", padx=4, pady=2)

        tk.Label(row, text=str(idx), width=3, anchor="e").pack(side="left", padx=(0, 6))

        x1, y1, x2, y2 = item["x1"], item["y1"], item["x2"], item["y2"]
        tk.Label(row, text=f"({x1}, {y1}, {x2}, {y2})", anchor="w", width=24).pack(side="left", padx=(0, 6))

        class_names = [name for name, _ in annotations.AVAILABLE_CLASSES]
        initial_class_name = annotations.class_name_for_id(item["class_id"])
        class_var = tk.StringVar(value=initial_class_name)
        item["class_var"] = class_var

        def on_class_changed(*args) -> None:
            class_name = class_var.get()
            self.__last_selected_class = class_name
            for name, cid in annotations.AVAILABLE_CLASSES:
                if name == class_name:
                    item["class_id"] = cid
                    break

        class_var.trace_add("write", on_class_changed)
        combo = ttk.Combobox(row, textvariable=class_var, values=class_names, state="readonly", width=14)
        combo.pack(side="left", padx=(0, 6))

        remove_btn = tk.Button(row, text="x", fg="red", command=lambda i=idx: self._remove_annotation(i))
        remove_btn.pack(side="left")

        self.__annotation_row_widgets.append(row)

    def _rebuild_annotation_list(self) -> None:
        """Clear and rebuild annotation list UI from __annotation_items."""
        for row in self.__annotation_row_widgets:
            row.destroy()
        self.__annotation_row_widgets.clear()
        for idx in range(len(self.__annotation_items)):
            self._add_annotation_row(idx)

    def _remove_annotation(self, idx: int) -> None:
        """Remove annotation item at idx, redraw canvas, rebuild list."""
        if idx >= len(self.__annotation_items):
            return
        self.__annotation_items.pop(idx)
        # Redraw canvas rectangles for remaining annotations
        self._redraw_annotation_rects()
        self._rebuild_annotation_list()

    def _redraw_annotation_rects(self) -> None:
        """Clear canvas rect/text/bg lists and redraw all annotation rects (without ROI labels)."""
        for rect_id in self.__selection_rects:
            self.image_canvas.delete(rect_id)
        self.__selection_rects.clear()
        for bg_id in self.__selection_bgs:
            self.image_canvas.delete(bg_id)
        self.__selection_bgs.clear()
        for text_id in self.__selection_texts:
            self.image_canvas.delete(text_id)
        self.__selection_texts.clear()

        for item in self.__annotation_items:
            x1, y1, x2, y2 = item["x1"], item["y1"], item["x2"], item["y2"]
            rect_id = self.image_canvas.create_rectangle(x1, y1, x2, y2, outline="green", width=2)
            self.__selection_rects.append(rect_id)

    def _clear_annotation_list_ui(self) -> None:
        """Remove all rows from annotation list and hide the frame."""
        for row in self.__annotation_row_widgets:
            row.destroy()
        self.__annotation_row_widgets.clear()
        if self.annotation_list_frame.winfo_ismapped():
            self.annotation_list_frame.pack_forget()

    # ------------------------------------------------------------------
    # Annotation mode entry / exit / submit
    # ------------------------------------------------------------------

    def enter_annotation_mode(self) -> None:
        """Enter annotation mode: freeze controls, clear canvas, load existing annotations."""
        self.__annotation_mode = True
        self.hide_annotate_button()
        self.show_submit_button()
        self.show_leave_annotation_button()
        self.show_remove_annotation_button()
        self._set_buttons_enabled(False)
        # submit_btn, leave_annotation_btn and remove_annotation_btn must stay enabled while in annotation mode
        self.submit_btn.config(state="normal")
        self.leave_annotation_btn.config(state="normal")
        self.remove_annotation_btn.config(state="normal")
        # Navigation buttons should be enabled in annotation mode
        self._set_navigation_buttons_enabled(True)

        # Clear canvas (does not clear annotation_items)
        self.__annotation_items.clear()
        self.clear_all()

        # Load existing annotations for the current frame
        self._load_frame_annotations()

    def leave_annotation_mode(self) -> None:
        """Exit annotation mode without submitting: restore normal controls."""
        self.__annotation_mode = False
        self.__annotation_items.clear()
        self._clear_annotation_list_ui()

        # Restore canvas to clean image
        self.clear_all()

        self.hide_submit_button()
        self.hide_leave_annotation_button()
        self.hide_remove_annotation_button()
        self.show_annotate_button()
        self._set_buttons_enabled(True)

        self.update_annotation_status()

    def _load_frame_annotations(self) -> None:
        """Load and display existing annotations for the current frame."""
        if self.__selected_image is None or self.__current_recording is None:
            return

        existing_boxes = annotations.load_annotations(self.__selected_image, self.__current_recording)
        if existing_boxes and self.__image_obj is not None:
            img_w = self.__image_obj.width()
            img_h = self.__image_obj.height()
            for box in existing_boxes:
                px1, py1, px2, py2 = annotations.yolo_to_pixels(box, img_w, img_h)
                self.__annotation_items.append(
                    {
                        "class_id": box.class_id,
                        "x1": px1,
                        "y1": py1,
                        "x2": px2,
                        "y2": py2,
                    }
                )
            self._redraw_annotation_rects()
            self._rebuild_annotation_list()

        # Show annotation list frame
        if not self.annotation_list_frame.winfo_ismapped():
            self.annotation_list_frame.pack(before=self.path_hint, fill="x", padx=self.content_pad, pady=(4, 4))

    def submit_annotations(self) -> None:
        """Submit annotations: save to dataset and stay in annotation mode."""
        if self.__selected_image is None or self.__current_recording is None:
            return

        if self.__image_obj is None:
            return

        img_w = self.__image_obj.width()
        img_h = self.__image_obj.height()

        boxes: list[annotations.AnnotationBox] = []
        for item in self.__annotation_items:
            # Resolve class_id from combobox if available
            class_id = item["class_id"]
            if "class_var" in item:
                class_name = item["class_var"].get()
                for name, cid in annotations.AVAILABLE_CLASSES:
                    if name == class_name:
                        class_id = cid
                        break
            box = annotations.pixels_to_yolo(item["x1"], item["y1"], item["x2"], item["y2"], img_w, img_h, class_id)
            boxes.append(box)

        annotations.save_annotations(self.__selected_image, self.__current_recording, boxes)

        # Stay in annotation mode: clear items and reload saved annotations
        self.__annotation_items.clear()
        self._clear_annotation_list_ui()
        self.clear_canvas_elements()
        self.__image_obj = tk.PhotoImage(file=self.__selected_image)
        self.set_image_preview()
        self._load_frame_annotations()

        self.update_annotation_status()
        self._update_stats_display()

    def remove_frame_annotation(self) -> None:
        """Remove annotation files for the current frame and reload the GUI."""
        if self.__selected_image is None or self.__current_recording is None:
            return

        removed = annotations.remove_annotation(self.__selected_image, self.__current_recording)
        if not removed:
            messagebox.showinfo("No Annotation", "This frame has no annotation to remove.")
            return

        # Clear annotation items and canvas selections
        self.__annotation_items.clear()
        self._clear_annotation_list_ui()
        self.clear_canvas_elements()
        self.__image_obj = tk.PhotoImage(file=self.__selected_image)
        self.set_image_preview()

        # Keep the annotation list frame visible (now empty)
        if not self.annotation_list_frame.winfo_ismapped():
            self.annotation_list_frame.pack(before=self.path_hint, fill="x", padx=self.content_pad, pady=(4, 4))

        # Reload stats and annotation status
        self.update_annotation_status()
        self._update_stats_display()

    # ------------------------------------------------------------------
    # Stats tooltip
    # ------------------------------------------------------------------

    def _update_stats_display(self) -> None:
        """Update the annotation stats display with new format."""
        stats = annotations.get_extended_dataset_stats()
        total = stats.train_total + stats.val_total

        total_pos = stats.train_positive + stats.val_positive

        # Calculate percentages for total train/val
        total_train_pct = round(100 * stats.train_total / total) if total else 0
        total_val_pct = 100 - total_train_pct if total else 0

        # Calculate percentages for total pos/neg
        total_pos_pct = round(100 * total_pos / total) if total else 0
        total_neg_pct = 100 - total_pos_pct if total else 0

        # Build the text content
        lines = [
            f"Total annotations: {total}",
            f"Total train/val: {total_train_pct}% / {total_val_pct}%",
            f"Total pos/neg: {total_pos_pct}% / {total_neg_pct}%",
        ]

        # Add per-class stats
        for class_info in stats.class_stats:
            class_total = class_info.train_count + class_info.val_count
            if class_total > 0:
                class_train_pct = round(100 * class_info.train_count / class_total)
                class_val_pct = 100 - class_train_pct
                lines.append(f"{class_info.name} annotations: {class_total}")
                lines.append(f"{class_info.name} train/val: {class_train_pct}% / {class_val_pct}%")

        text = "\n".join(lines)

        # Update the Text widget (need to enable it to edit)
        self.stats_text.config(state="normal")
        self.stats_text.delete("1.0", "end")
        self.stats_text.insert("1.0", text)
        self.stats_text.config(state="disabled")

    # ------------------------------------------------------------------
    # Model selection and initialization
    # ------------------------------------------------------------------

    def _init_detector(self) -> None:
        """Initialize detector with currently selected model."""
        if self.__selected_model_info is None:
            # On first initialization, try to find the newest fine-tuned model or use base
            models = fine_tune.get_available_models()
            if models:
                self.__selected_model_info = models[0]

        if self.__selected_model_info is None or self.__selected_model_info["is_base"]:
            # Use base model
            self.detector = BirdDetector()
        else:
            # Use fine-tuned model
            model_path = self.__selected_model_info["model_path"]
            classes = list(range(len(self.__selected_model_info["classes"])))
            self.detector = BirdDetector(model_path=model_path, classes=classes)

    def open_model_select_dialog(self) -> None:
        """Open the model selection dialog."""
        dialog = ModelSelectDialog(self.root)
        result = dialog.wait()
        if result is not None:
            self.__selected_model_info = result
            self._init_detector()
            messagebox.showinfo("Model Selected", f"Using model: {result['version']}\n{result['description']}")

    # ------------------------------------------------------------------
    # Fine-tune model
    # ------------------------------------------------------------------

    def open_fine_tune_dialog(self) -> None:
        """Open the fine-tune modal dialog and start training if confirmed."""
        dialog = FineTuneDialog(self.root)
        result = dialog.wait()
        if result is None:
            return
        version, description, preset_path = result
        self.start_fine_tune(version, description, preset_path)

    def start_fine_tune(self, version: str, description: str, preset_path: Path | None) -> None:
        """Disable UI and start fine-tuning in a background thread."""
        self._fine_tune_version = version
        self._fine_tune_description = description
        self._fine_tune_preset_path = preset_path
        self._fine_tune_error: str | None = None
        self._fine_tune_result: Path | None = None

        self._set_buttons_enabled(False)

        self._fine_tune_progress = tk.Toplevel(self.root)
        self._fine_tune_progress.title("Fine Tuning")
        self._fine_tune_progress.transient(self.root)
        self._fine_tune_progress.grab_set()
        self._fine_tune_progress.resizable(False, False)
        self._fine_tune_progress.protocol("WM_DELETE_WINDOW", lambda: None)

        frame = tk.Frame(self._fine_tune_progress, padx=24, pady=24)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text=f"Fine-tuning model {version}...", font=("Helvetica", 12)).pack(pady=(0, 12))

        self._ft_phase_var = tk.StringVar(value="Preparing...")
        tk.Label(frame, textvariable=self._ft_phase_var, fg="#444444").pack(pady=(0, 8))

        self._ft_epoch_var = tk.StringVar(value="")
        tk.Label(frame, textvariable=self._ft_epoch_var, fg="#666666", font=("TkDefaultFont", 9)).pack(pady=(0, 8))

        self._ft_bar = ttk.Progressbar(frame, length=360, mode="determinate", maximum=100)
        self._ft_bar.pack(pady=(0, 4))

        tk.Label(
            frame, text="Training output is also printed to the terminal.", fg="#888888", font=("TkDefaultFont", 8)
        ).pack(pady=(4, 0))

        self._fine_tune_progress.update_idletasks()
        px = self.root.winfo_x() + (self.root.winfo_width() - self._fine_tune_progress.winfo_width()) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - self._fine_tune_progress.winfo_height()) // 2
        self._fine_tune_progress.geometry(f"+{px}+{py}")

        self._fine_tune_thread = threading.Thread(target=self._run_fine_tune, daemon=True)
        self._fine_tune_thread.start()
        self.root.after(200, self._check_fine_tune_complete)

    def _on_fine_tune_epoch(self, current: int, total: int) -> None:
        """Update progress dialog from background thread (thread-safe via root.after)."""

        def _update() -> None:
            if not self._fine_tune_progress.winfo_exists():
                return
            pct = int(100 * current / total)
            self._ft_phase_var.set("Training...")
            self._ft_epoch_var.set(f"Epoch {current}/{total}")
            self._ft_bar["value"] = pct

        self.root.after(0, _update)

    def _run_fine_tune(self) -> None:
        """Execute fine-tuning in background thread."""
        self.root.after(
            0,
            lambda: self._ft_phase_var.set("Preparing dataset...") if self._fine_tune_progress.winfo_exists() else None,
        )
        try:
            self._fine_tune_result = fine_tune.run_fine_tune(
                self._fine_tune_version,
                self._fine_tune_description,
                self._fine_tune_preset_path,
                on_epoch=self._on_fine_tune_epoch,
            )
        except Exception as exc:
            self._fine_tune_error = str(exc)

    def _check_fine_tune_complete(self) -> None:
        """Poll for fine-tune thread completion and clean up."""
        if self._fine_tune_thread.is_alive():
            self.root.after(500, self._check_fine_tune_complete)
            return

        if self._fine_tune_progress.winfo_exists():
            self._fine_tune_progress.grab_release()
            self._fine_tune_progress.destroy()

        self._set_buttons_enabled(True)

        if self._fine_tune_error:
            messagebox.showerror("Fine Tune Error", self._fine_tune_error)
        else:
            messagebox.showinfo(
                "Fine Tune Complete",
                f"Model saved to:\n{self._fine_tune_result}",
            )

    def run(self) -> None:
        self.root.mainloop()
