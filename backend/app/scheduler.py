from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from . import models, rotation
from .config import TIMEZONE
from .database import SessionLocal
from .push_service import send_push

JOB_ID = "daily_feeding_check"


def check_and_notify() -> None:
    db = SessionLocal()
    try:
        today = rotation.today_chile()
        day = rotation.get_or_create_feeding_day(db, today)
        if day.fed:
            return

        person = day.assigned_person
        subs = (
            db.query(models.PushSubscription)
            .filter(models.PushSubscription.person_id == person.id)
            .all()
        )
        if not subs:
            print(f"[scheduler] {person.name} no tiene suscripciones push registradas.")
            return

        for sub in subs:
            result = send_push(
                sub,
                title="🐶 ¡Hora de darle comida al perro!",
                body=f"Hoy te toca a vos, {person.name}. Todavía no está marcado como hecho.",
            )
            if result == "expired":
                db.delete(sub)

        day.notified_at = rotation.now_chile()
        db.commit()
    finally:
        db.close()


def _read_notify_time() -> tuple[int, int]:
    db = SessionLocal()
    try:
        settings = db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
        if settings:
            return settings.notify_hour, settings.notify_minute
        return 20, 0
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=TIMEZONE)
    hour, minute = _read_notify_time()
    scheduler.add_job(
        check_and_notify,
        CronTrigger(hour=hour, minute=minute, timezone=TIMEZONE),
        id=JOB_ID,
        replace_existing=True,
    )
    scheduler.start()
    return scheduler


def reschedule(scheduler: BackgroundScheduler, hour: int, minute: int) -> None:
    """Se llama cuando alguien cambia la hora del aviso desde Ajustes."""
    scheduler.add_job(
        check_and_notify,
        CronTrigger(hour=hour, minute=minute, timezone=TIMEZONE),
        id=JOB_ID,
        replace_existing=True,
    )
