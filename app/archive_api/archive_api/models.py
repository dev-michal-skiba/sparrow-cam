from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BirdClass(StrEnum):
    great_tit = "great_tit"
    house_sparrow = "house_sparrow"
    pigeon = "pigeon"
    eurasian_nuthatch = "eurasian_nuthatch"


class BoundingBox(BaseModel):
    x: Annotated[float, Field(ge=0.0, le=1.0)]
    y: Annotated[float, Field(ge=0.0, le=1.0)]
    width: Annotated[float, Field(gt=0.0, le=1.0)]
    height: Annotated[float, Field(gt=0.0, le=1.0)]

    @model_validator(mode="after")
    def check_bounds_within_frame(self) -> "BoundingBox":
        if self.x + self.width > 1.0:
            raise ValueError("x + width must not exceed 1.0")
        if self.y + self.height > 1.0:
            raise ValueError("y + height must not exceed 1.0")
        return self


class ROIAnnotation(BaseModel):
    bird_class: BirdClass
    bbox: BoundingBox


class Detection(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    bird_class: str = Field(alias="class")


class ManualAnnotationsRequest(BaseModel):
    manual_annotations: dict[str, list[ROIAnnotation]]


class MetaFile(BaseModel):
    detections: dict[str, list[Detection]] = {}
    manual_annotations: dict[str, list[ROIAnnotation]] | None = None
