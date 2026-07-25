"""
Migracion y siembra inicial de la base de datos. Todo acá es idempotente:
seguro de correr en cada arranque, tanto en una instalacion nueva como en
una que ya tiene datos reales de la familia.
"""
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from . import models
from .config import NOTIFY_HOUR, NOTIFY_MINUTE, PEOPLE, WEEKDAY_SCHEDULE


def ensure_schema(engine: Engine) -> None:
    """Agrega columnas nuevas a tablas que ya existian antes de esta
    version, sin tocar los datos existentes."""
    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(people)"))]
        if "color" not in cols:
            conn.execute(text("ALTER TABLE people ADD COLUMN color VARCHAR"))
            conn.commit()


def seed_people(db: Session) -> None:
    for name in PEOPLE:
        exists = db.query(models.Person).filter(models.Person.name == name).first()
        if not exists:
            db.add(models.Person(name=name, active=True))
    db.commit()


def seed_weekday_schedule(db: Session) -> None:
    """Si la tabla esta vacia (instalacion nueva o que recien actualiza a
    esta version), la llena con la rotacion que tenia config.py, para que
    nadie note un cambio al actualizar. De ahi en adelante se edita solo
    desde Ajustes."""
    if db.query(models.WeekdaySchedule).count() > 0:
        return

    for weekday, person_name in WEEKDAY_SCHEDULE.items():
        person = db.query(models.Person).filter(models.Person.name == person_name).first()
        if person is None:
            continue
        db.add(models.WeekdaySchedule(weekday=weekday, person_id=person.id))
    db.commit()


def seed_app_settings(db: Session) -> None:
    existing = db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
    if existing:
        return
    db.add(
        models.AppSettings(
            id=1,
            notify_hour=NOTIFY_HOUR,
            notify_minute=NOTIFY_MINUTE,
        )
    )
    db.commit()


def run_all(engine: Engine, db: Session) -> None:
    ensure_schema(engine)
    seed_people(db)
    seed_weekday_schedule(db)
    seed_app_settings(db)
