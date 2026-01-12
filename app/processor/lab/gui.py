import functools
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from lab.constants import IMAGES_DIR
from lab.exception import UserFacingError
from lab.utils import Region, get_annotated_image_bytes, validate_selected_image
from processor.bird_detector import BirdDetector


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
        self.__selection_regions: list[tuple[int, int, int, int]] = []  # List of (x1, y1, x2, y2)

        # Crosshair lines for selection guidance
        self.__crosshair_h: int | None = None  # Horizontal line ID
        self.__crosshair_v: int | None = None  # Vertical line ID

        # Dimension label shown while drawing selection
        self.__dimension_text: int | None = None  # Canvas text ID

        # UI components
        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=(24, 12))

        self.select_btn = tk.Button(self.button_frame, text="Select image", command=self.choose_file)
        self.select_btn.pack(side="left", padx=(0, 8))

        self.detect_btn = tk.Button(self.button_frame, text="Detect Bird", command=self.detect_bird)

        self.clear_btn = tk.Button(self.button_frame, text="Clear", command=self.clear_all)

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

    def get_selected_file_from_user(self) -> Path | None:
        path = filedialog.askopenfilename(
            initialdir=str(IMAGES_DIR),
            filetypes=[("PNG images", "*.png")],
            title="Select image",
        )
        return Path(path) if path else None

    def set_selected_image(self, path: Path) -> None:
        self.__selected_image = path.resolve()
        self.__selected_image_text.set(str(self.__selected_image))

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

        # Raise selection rectangles and ROI texts above the image so they remain visible
        for rect_id in self.__selection_rects:
            self.image_canvas.tag_raise(rect_id)
        for text_id in self.__selection_texts:
            self.image_canvas.tag_raise(text_id)
        if self.__current_rect is not None:
            self.image_canvas.tag_raise(self.__current_rect)

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
        """Update selection rectangle while dragging."""
        if self.__selection_start is None or self.__current_rect is None:
            return
        x1, y1 = self.__selection_start
        x2, y2 = event.x, event.y
        self.image_canvas.coords(self.__current_rect, x1, y1, x2, y2)

        # Calculate normalized ROI coordinates
        roi_x1, roi_x2 = min(x1, x2), max(x1, x2)
        roi_y1, roi_y2 = min(y1, y2), max(y1, y2)
        # Position text at the top-left corner of the rectangle
        text_x = roi_x1 + 4
        text_y = roi_y1 + 4
        roi_str = f"ROI: ({roi_x1}, {roi_y1}, {roi_x2}, {roi_y2})"

        if self.__dimension_text is None:
            self.__dimension_text = self.image_canvas.create_text(
                text_x,
                text_y,
                text=roi_str,
                anchor="nw",
                fill="blue",
                font=("TkDefaultFont", 10, "bold"),
            )
        else:
            self.image_canvas.coords(self.__dimension_text, text_x, text_y)
            self.image_canvas.itemconfig(self.__dimension_text, text=roi_str)

    def on_selection_end(self, event) -> None:
        """Finalize selection rectangle and add to the list of regions."""
        if self.__selection_start is None or self.__image_obj is None:
            return

        x1, y1 = self.__selection_start
        x2, y2 = event.x, event.y

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

        # Only add region if it's a meaningful selection (at least 10x10 pixels)
        if (x2 - x1) >= 10 and (y2 - y1) >= 10:
            self.__selection_regions.append((x1, y1, x2, y2))
            self.__selection_rects.append(self.__current_rect)
            self.__current_rect = None
            # Keep the ROI text and add to finalized list
            if self.__dimension_text is not None:
                # Update text with clamped coordinates
                roi_str = f"ROI: ({x1}, {y1}, {x2}, {y2})"
                self.image_canvas.itemconfig(self.__dimension_text, text=roi_str)
                self.image_canvas.coords(self.__dimension_text, x1 + 4, y1 + 4)
                self.__selection_texts.append(self.__dimension_text)
                self.__dimension_text = None
            self.show_clear_button()
        else:
            # Too small, delete the rectangle and text
            if self.__current_rect is not None:
                self.image_canvas.delete(self.__current_rect)
                self.__current_rect = None
            self.hide_dimension_text()

        self.__selection_start = None

    def hide_dimension_text(self) -> None:
        """Remove the dimension text from the canvas."""
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

    @handle_user_error
    def choose_file(self) -> None:
        """Open a file dialog and update the preview if a valid PNG is selected."""
        path = self.get_selected_file_from_user()
        validate_selected_image(path)
        self.set_selected_image(path)
        self.__image_obj = tk.PhotoImage(file=self.__selected_image)
        self.clear_all()
        self.set_image_preview()
        self.show_detect_button()

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

    def run(self) -> None:
        self.root.mainloop()
