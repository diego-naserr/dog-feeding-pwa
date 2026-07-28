import os
from datetime import datetime, time, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import bootstrap, models, rotation, scheduler as scheduler_module, schemas
from .database import Base, SessionLocal, engine, get_db
from .push_service import send_push

BASE_DIR = Path(__file__).resolve().parent.parent

Base.metadata.create_all(bind=engine)

_bootstrap_db = SessionLocal()
try:
    bootstrap.run_all(engine, _bootstrap_db)
finally:
    _bootstrap_db.close()

app = FastAPI(title="Turno de Comida - Perros")
scheduler = scheduler_module.start_scheduler()


def _today_out(day: models.FeedingDay) -> schemas.TodayOut:
    return schemas.TodayOut(
        date=day.date,
        assigned_person=day.assigned_person,
        fed=day.fed,
        fed_by=day.fed_by_person,
        fed_at=day.fed_at,
    )


def _get_settings(db: Session) -> models.AppSettings:
    settings = db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
    if settings is None:
        settings = models.AppSettings(id=1, notify_hour=20, notify_minute=0)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@app.get("/api/vapid-public-key")
def vapid_public_key():
    return {"publicKey": os.environ["VAPID_PUBLIC_KEY"]}


# ==================== PERSONAS ====================


@app.get("/api/people", response_model=list[schemas.PersonOut])
def get_people(include_inactive: bool = False, db: Session = Depends(get_db)):
    query = db.query(models.Person)
    if not include_inactive:
        query = query.filter(models.Person.active.is_(True))
    return query.order_by(models.Person.id).all()


@app.post("/api/people", response_model=schemas.PersonOut)
def create_person(req: schemas.PersonCreate, db: Session = Depends(get_db)):
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "El nombre no puede estar vacío")

    existing = db.query(models.Person).filter(models.Person.name == name).first()
    if existing:
        if existing.active:
            raise HTTPException(400, "Ya existe una persona con ese nombre")
        existing.active = True
        existing.color = req.color or existing.color
        db.commit()
        db.refresh(existing)
        return existing

    person = models.Person(name=name, active=True, color=req.color)
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


@app.patch("/api/people/{person_id}", response_model=schemas.PersonOut)
def update_person(person_id: int, req: schemas.PersonUpdate, db: Session = Depends(get_db)):
    person = db.query(models.Person).filter(models.Person.id == person_id).first()
    if not person:
        raise HTTPException(404, "Persona no encontrada")

    if req.active is False and person.active:
        assigned = (
            db.query(models.WeekdaySchedule)
            .filter(models.WeekdaySchedule.person_id == person_id)
            .count()
        )
        if assigned > 0:
            raise HTTPException(
                400,
                f"{person.name} todavía tiene días asignados en la rotación semanal. "
                "Reasigná esos días a otra persona antes de desactivarla.",
            )

    if req.name is not None:
        new_name = req.name.strip()
        if not new_name:
            raise HTTPException(400, "El nombre no puede estar vacío")
        dup = (
            db.query(models.Person)
            .filter(models.Person.name == new_name, models.Person.id != person_id)
            .first()
        )
        if dup:
            raise HTTPException(400, "Ya existe una persona con ese nombre")
        person.name = new_name

    if req.color is not None:
        person.color = req.color

    if req.active is not None:
        person.active = req.active

    db.commit()
    db.refresh(person)
    return person


# ==================== ROTACIÓN SEMANAL ====================

WEEKDAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


@app.get("/api/schedule", response_model=list[schemas.ScheduleItemOut])
def get_schedule(db: Session = Depends(get_db)):
    rows = (
        db.query(models.WeekdaySchedule)
        .order_by(models.WeekdaySchedule.weekday)
        .all()
    )
    return [schemas.ScheduleItemOut(weekday=r.weekday, person=r.person) for r in rows]


@app.put("/api/schedule", response_model=list[schemas.ScheduleItemOut])
def update_schedule(items: list[schemas.ScheduleItemIn], db: Session = Depends(get_db)):
    weekdays = {item.weekday for item in items}
    if weekdays != set(range(7)):
        raise HTTPException(400, "Hay que asignar una persona para los 7 días de la semana")

    people_ids = {p.id for p in db.query(models.Person).filter(models.Person.active.is_(True))}
    for item in items:
        if item.person_id not in people_ids:
            raise HTTPException(400, "Una de las personas asignadas no existe o está inactiva")

    for item in items:
        row = (
            db.query(models.WeekdaySchedule)
            .filter(models.WeekdaySchedule.weekday == item.weekday)
            .first()
        )
        if row:
            row.person_id = item.person_id
        else:
            db.add(models.WeekdaySchedule(weekday=item.weekday, person_id=item.person_id))
    db.commit()

    rows = (
        db.query(models.WeekdaySchedule)
        .order_by(models.WeekdaySchedule.weekday)
        .all()
    )
    return [schemas.ScheduleItemOut(weekday=r.weekday, person=r.person) for r in rows]


# ==================== AJUSTES ====================


@app.get("/api/settings", response_model=schemas.SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    return _get_settings(db)


@app.put("/api/settings", response_model=schemas.SettingsOut)
def update_settings(req: schemas.SettingsUpdate, db: Session = Depends(get_db)):
    whatsapp_url = (req.whatsapp_group_url or "").strip() or None
    if whatsapp_url and not whatsapp_url.startswith("http"):
        raise HTTPException(400, "El link tiene que empezar con http:// o https://")

    settings = _get_settings(db)
    settings.notify_hour = req.notify_hour
    settings.notify_minute = req.notify_minute
    settings.reminder_hour = req.reminder_hour
    settings.reminder_minute = req.reminder_minute
    settings.whatsapp_group_url = whatsapp_url
    db.commit()
    db.refresh(settings)

    scheduler_module.reschedule(
        scheduler,
        req.notify_hour,
        req.notify_minute,
        req.reminder_hour,
        req.reminder_minute,
    )
    return settings


# ==================== HOY / HISTORIAL ====================


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


@app.delete("/api/feed", response_model=schemas.TodayOut)
def unmark_fed(db: Session = Depends(get_db)):
    """Deshace la marca de 'ya le dieron comida' de hoy, por si alguien
    se equivocó al tocar el botón."""
    day = rotation.get_or_create_feeding_day(db, rotation.today_chile())
    if not day.fed:
        raise HTTPException(400, "Hoy todavía no está marcado como hecho")

    day.fed = False
    day.fed_by_person_id = None
    day.fed_at = None
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


@app.post("/api/test-push")
def test_push(req: schemas.TestPushRequest, db: Session = Depends(get_db)):
    person = db.query(models.Person).filter(models.Person.name == req.person_name).first()
    if not person:
        raise HTTPException(404, "Persona no encontrada")

    subs = (
        db.query(models.PushSubscription)
        .filter(models.PushSubscription.person_id == person.id)
        .all()
    )
    if not subs:
        return {"sent": 0, "message": "Este dispositivo todavía no está suscrito a notificaciones"}

    sent = 0
    for sub in subs:
        result = send_push(
            sub,
            title="🐾 Notificación de prueba",
            body="Si ves esto, las notificaciones están funcionando bien.",
        )
        if result == "ok":
            sent += 1
        elif result == "expired":
            db.delete(sub)
    db.commit()

    if sent == 0:
        return {"sent": 0, "message": "No se pudo enviar. Revisá el permiso de notificaciones."}
    return {"sent": sent, "message": "Notificación de prueba enviada"}


@app.get("/api/history", response_model=list[schemas.HistoryItem])
def get_history(days: int = 30, db: Session = Depends(get_db)):
    settings = _get_settings(db)
    cutoff_hour = settings.reminder_hour
    cutoff_minute = settings.reminder_minute

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
                day.date, time(hour=cutoff_hour, minute=cutoff_minute)
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
