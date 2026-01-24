from lab.constants import ARCHIVE_DIR, IMAGES_DIR
from lab.gui import LabGUI

ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
gui = LabGUI()
gui.run()
