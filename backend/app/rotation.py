from datetime import date as date_cls
from datetime import datetime

from sqlalchemy.orm import Session

from . import models
from .config import TIMEZONE, WEEKDAY_SCHEDULE


def today_chile() -> date_cls:
    return datetime.now(TIMEZONE).date()


def now_chile() -> datetime:
    """Datetime naive en hora de Chile (sin tzinfo) para guardar en SQLite
    sin ambigüedad, ya que toda la app opera en una sola zona horaria."""
    return datetime.now(TIMEZONE).replace(tzinfo=None)


def assigned_name_for_date(d: date_cls) -> str:
    return WEEKDAY_SCHEDULE[d.weekday()]


def get_or_create_feeding_day(db: Session, d: date_cls) -> models.FeedingDay:
    day = db.query(models.FeedingDay).filter(models.FeedingDay.date == d).first()
    if day:
        return day

    assigned_name = assigned_name_for_date(d)
    person = db.query(models.Person).filter(models.Person.name == assigned_name).first()
    if person is None:
        raise ValueError(
            f"La persona '{assigned_name}' está en WEEKDAY_SCHEDULE pero no en PEOPLE (config.py)"
        )

    day = models.FeedingDay(date=d, assigned_person_id=person.id, fed=False)
    db.add(day)
    db.commit()
    db.refresh(day)
    return day
