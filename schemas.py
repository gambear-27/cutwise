from pydantic import BaseModel, Field


class PartDimension(BaseModel):
    width: float = Field(..., description="2D width of the part")
    length: float = Field(..., description="2D length of the part")


class PartItem(BaseModel):
    part_id: str = Field(..., description="Unique identifier for the part")
    name: str = Field(..., description="Descriptive name of the CAD part/entity")
    dimensions: PartDimension = Field(..., description="Flat 2D bounding box dimensions")
    quantity: int = Field(default=1, description="Quantity of identical parts")
    allow_rotation: bool = Field(default=True, description="Whether rotation is permitted for nesting")
