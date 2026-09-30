from typing import List, Optional
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    width: float = Field(..., description="2D bounding box width of the part")
    length: float = Field(..., description="2D bounding box length of the part")


# Backwards compatibility alias
PartDimension = BoundingBox


class PartItem(BaseModel):
    part_id: str = Field(..., description="Unique identifier for the part")
    name: str = Field(..., description="Descriptive name of the CAD part/entity")
    thickness: float = Field(default=0.0, description="Extracted Z-axis thickness / depth of the material")
    radius: Optional[float] = Field(default=None, description="Calculated radius of curved features if applicable")
    contour: List[List[float]] = Field(
        ...,
        description="Ordered list of 2D [x, y] vertices defining the exact outer 2D contour"
    )
    holes: List[List[List[float]]] = Field(
        default_factory=list,
        description="List of inner hole polygon vertex loops"
    )
    bounding_box: BoundingBox = Field(..., description="Flat 2D bounding box dimensions")
    svg_path: Optional[str] = Field(
        default=None,
        description="Complete SVG string output with vector paths and text labels for thickness & radius"
    )
    quantity: int = Field(default=1, description="Quantity of identical parts")
    allow_rotation: bool = Field(default=True, description="Whether rotation is permitted for nesting")

    @property
    def dimensions(self) -> BoundingBox:
        """Backwards compatibility property for dimensions."""
        return self.bounding_box
