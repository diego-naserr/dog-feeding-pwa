from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class PersonOut(BaseModel):
    id: int
    name: str
    color: Optional[str] = None
    active: bool = True

    class Config:
        from_attributes = True


class PersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    color: Optional[str] = None


class PersonUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=40)
    color: Optional[str] = None
    active: Optional[bool] = None


class TodayOut(BaseModel):
    date: date
    assigned_person: PersonOut
    fed: bool
    fed_by: Optional[PersonOut] = None
    fed_at: Optional[datetime] = None


class FeedRequest(BaseModel):
    person_name: str


class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionIn(BaseModel):
    person_name: str
    endpoint: str
    keys: SubscriptionKeys


class HistoryItem(BaseModel):
    date: date
    assigned_person: str
    fed: bool
    fed_by: Optional[str] = None
    fed_at: Optional[datetime] = None
    on_time: Optional[bool] = None


class ScheduleItemOut(BaseModel):
    weekday: int
    person: PersonOut


class ScheduleItemIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    person_id: int


class SettingsOut(BaseModel):
    notify_hour: int
    notify_minute: int


class SettingsUpdate(BaseModel):
    notify_hour: int = Field(ge=0, le=23)
    notify_minute: int = Field(ge=0, le=59)


class TestPushRequest(BaseModel):
    person_name: str
