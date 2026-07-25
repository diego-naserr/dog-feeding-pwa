from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from . import models, rotation
from .config import NOTIFY_HOUR, NOTIFY_MINUTE, TIMEZONE
from .database import SessionLocal
from .push_service import send_push


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


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        check_and_notify,
        CronTrigger(hour=NOTIFY_HOUR, minute=NOTIFY_MINUTE, timezone=TIMEZONE),
        id="daily_feeding_check",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
