import functools
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from lab.constants import IMAGES_DIR
from lab.exception import UserFacingError
from lab.utils import get_annotated_image_bytes, validate_selected_image
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

        # UI components
        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=(24, 12))

        self.select_btn = tk.Button(self.button_frame, text="Select image", command=self.choose_file)
        self.select_btn.pack(side="left", padx=(0, 8))

        self.detect_btn = tk.Button(self.button_frame, text="Detect Bird", command=self.detect_bird)

        self.image_preview = tk.Label(self.root)
        self.image_preview.pack(padx=24, pady=(0, 24))

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
        self.image_preview.config(image=self.__image_obj)
        self.image_preview.image = self.__image_obj

    def show_detect_button(self) -> None:
        if not self.detect_btn.winfo_ismapped():
            self.detect_btn.pack(side="left")

    @handle_user_error
    def choose_file(self) -> None:
        """Open a file dialog and update the preview if a valid PNG is selected."""
        path = self.get_selected_file_from_user()
        validate_selected_image(path)
        self.set_selected_image(path)
        self.__image_obj = tk.PhotoImage(file=self.__selected_image)
        self.set_image_preview()
        self.show_detect_button()

    @handle_user_error
    def detect_bird(self) -> None:
        self.__image_obj = tk.PhotoImage(
            data=get_annotated_image_bytes(self.detector, self.__selected_image),
            format="png",
        )
        self.set_image_preview()

    def run(self) -> None:
        self.root.mainloop()
