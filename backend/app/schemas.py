from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class PersonOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


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
