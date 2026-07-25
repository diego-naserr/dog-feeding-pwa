import os
from datetime import datetime, time, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import models, rotation, schemas
from .config import ON_TIME_CUTOFF_HOUR, ON_TIME_CUTOFF_MINUTE, PEOPLE, TIMEZONE
from .database import Base, SessionLocal, engine, get_db
from .scheduler import start_scheduler

BASE_DIR = Path(__file__).resolve().parent.parent

Base.metadata.create_all(bind=engine)


def seed_people() -> None:
    db = SessionLocal()
    try:
        for name in PEOPLE:
            exists = db.query(models.Person).filter(models.Person.name == name).first()
            if not exists:
                db.add(models.Person(name=name, active=True))
        db.commit()
    finally:
        db.close()


seed_people()

app = FastAPI(title="Turno de Comida - Perros")
scheduler = start_scheduler()


def _today_out(day: models.FeedingDay) -> schemas.TodayOut:
    return schemas.TodayOut(
        date=day.date,
        assigned_person=day.assigned_person,
        fed=day.fed,
        fed_by=day.fed_by_person,
        fed_at=day.fed_at,
    )


@app.get("/api/vapid-public-key")
def vapid_public_key():
    return {"publicKey": os.environ["VAPID_PUBLIC_KEY"]}


@app.get("/api/people", response_model=list[schemas.PersonOut])
def get_people(db: Session = Depends(get_db)):
    return db.query(models.Person).filter(models.Person.active.is_(True)).all()


@app.get("/api/today", response_model=schemas.TodayOut)
def get_today(db: Session = Depends(get_db)):
    day = rotation.get_or_create_feeding_day(db, rotation.today_chile())
    return _today_out(day)


@app.post("/api/feed", response_model=schemas.TodayOut)
def mark_fed(req: schemas.FeedRequest, db: Session = Depends(get_db)):
    person = db.query(models.Person).filter(models.Person.name == req.person_name).first()
    if not person:
        raise HTTPException(404, "Persona no encontrada")

    day = rotation.get_or_create_feeding_day(db, rotation.today_chile())
    day.fed = True
    day.fed_by_person_id = person.id
    day.fed_at = rotation.now_chile()
    db.commit()
    db.refresh(day)
    return _today_out(day)


@app.post("/api/subscribe")
def subscribe(sub: schemas.PushSubscriptionIn, db: Session = Depends(get_db)):
    person = db.query(models.Person).filter(models.Person.name == sub.person_name).first()
    if not person:
        raise HTTPException(404, "Persona no encontrada")

    existing = (
        db.query(models.PushSubscription)
        .filter(models.PushSubscription.endpoint == sub.endpoint)
        .first()
    )
    if existing:
        existing.person_id = person.id
        existing.p256dh = sub.keys.p256dh
        existing.auth = sub.keys.auth
    else:
        db.add(
            models.PushSubscription(
                person_id=person.id,
                endpoint=sub.endpoint,
                p256dh=sub.keys.p256dh,
                auth=sub.keys.auth,
                created_at=rotation.now_chile(),
            )
        )
    db.commit()
    return {"ok": True}


@app.get("/api/history", response_model=list[schemas.HistoryItem])
def get_history(days: int = 30, db: Session = Depends(get_db)):
    today = rotation.today_chile()
    start = today - timedelta(days=days - 1)
    rows = (
        db.query(models.FeedingDay)
        .filter(models.FeedingDay.date >= start, models.FeedingDay.date <= today)
        .order_by(models.FeedingDay.date.desc())
        .all()
    )

    result = []
    for day in rows:
        on_time = None
        if day.fed and day.fed_at:
            cutoff = datetime.combine(
                day.date, time(hour=ON_TIME_CUTOFF_HOUR, minute=ON_TIME_CUTOFF_MINUTE)
            )
            on_time = day.fed_at <= cutoff
        result.append(
            schemas.HistoryItem(
                date=day.date,
                assigned_person=day.assigned_person.name,
                fed=day.fed,
                fed_by=day.fed_by_person.name if day.fed_by_person else None,
                fed_at=day.fed_at,
                on_time=on_time,
            )
        )
    return result


app.mount("/", StaticFiles(directory=str(BASE_DIR / "static"), html=True), name="static")
