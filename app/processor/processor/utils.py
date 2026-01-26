import json

from processor.constants import DETECTION_PRESET_PATH


def load_detection_preset() -> dict:
    """Load detection preset from JSON file.

    Returns:
        dict: Preset containing 'params' (detection parameters) and 'regions' (detection regions).
    """
    with open(DETECTION_PRESET_PATH) as f:
        return json.load(f)
