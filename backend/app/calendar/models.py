from datetime import datetime
from pydantic import BaseModel, Field


class CalendarEventCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    all_day: bool = False
    recurrence: str | None = Field(default=None, max_length=50)


class CalendarEventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    all_day: bool | None = None
    recurrence: str | None = Field(default=None, max_length=50)


class BulkDeleteBody(BaseModel):
    event_ids: list[int]


class CalendarEventOut(BaseModel):
    id: int
    title: str
    description: str | None
    start_time: datetime
    end_time: datetime | None
    all_day: bool
    recurrence: str | None
    created_at: datetime
