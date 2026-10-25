"""Request and response bodies for the event endpoints (PRD §5.4 event schema)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

Name = Annotated[str, Field(min_length=1, max_length=64)]


class EventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: uuid.UUID
    site: Name
    camera: Name
    zone: Name
    type: Literal["red_zone_intrusion"]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    bbox: tuple[float, float, float, float]
    occurred_at: AwareDatetime

    @field_validator("bbox")
    @classmethod
    def _corners_ordered(cls, bbox: tuple[float, float, float, float]):
        x1, y1, x2, y2 = bbox
        if not (x1 < x2 and y1 < y2):
            raise ValueError("bbox must be [x1, y1, x2, y2] with x1 < x2 and y1 < y2")
        return bbox


class EventOut(EventIn):
    received_at: datetime


class EventPage(BaseModel):
    items: list[EventOut]
    next: str | None = Field(description="Cursor for the next (older) page; null on the last.")
