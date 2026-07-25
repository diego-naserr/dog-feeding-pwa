from datetime import date as date_cls
from datetime import datetime

from sqlalchemy.orm import Session

from . import models
from .config import TIMEZONE


def today_chile() -> date_cls:
    return datetime.now(TIMEZONE).date()


def now_chile() -> datetime:
    """Datetime naive en hora de Chile (sin tzinfo) para guardar en SQLite
    sin ambigüedad, ya que toda la app opera en una sola zona horaria."""
    return datetime.now(TIMEZONE).replace(tzinfo=None)


def assigned_person_for_date(db: Session, d: date_cls) -> models.Person:
    entry = (
        db.query(models.WeekdaySchedule)
        .filter(models.WeekdaySchedule.weekday == d.weekday())
        .first()
    )
    if entry is None:
        raise ValueError(
            f"No hay nadie asignado para el dia de la semana {d.weekday()} "
            "(Ajustes → Rotación semanal)"
        )
    return entry.person


def get_or_create_feeding_day(db: Session, d: date_cls) -> models.FeedingDay:
    day = db.query(models.FeedingDay).filter(models.FeedingDay.date == d).first()
    if day:
        return day

    person = assigned_person_for_date(db, d)
    day = models.FeedingDay(date=d, assigned_person_id=person.id, fed=False)
    db.add(day)
    db.commit()
    db.refresh(day)
    return day
