from typing import NamedTuple


class DetectionBox(NamedTuple):
    x1: int
    y1: int
    x2: int
    y2: int
    class_id: int
