from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from . import models, rotation
from .config import TIMEZONE
from .database import SessionLocal
from .push_service import send_push

NOTIFY_JOB_ID = "daily_feeding_check"
ESCALATE_JOB_ID = "daily_feeding_escalation"


def check_and_notify() -> None:
    """Aviso principal: solo a quien le toca ese dia."""
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


def check_and_escalate() -> None:
    """Segundo aviso: si a esta hora sigue sin marcarse, le llega a TODOS
    los que tengan notificaciones activas (no solo a quien le tocaba).
    Al tocarla, abre la app (el link de WhatsApp, si esta configurado,
    solo se usa para el boton "Abrir grupo de WhatsApp" en Hoy)."""
    db = SessionLocal()
    try:
        today = rotation.today_chile()
        day = rotation.get_or_create_feeding_day(db, today)
        if day.fed:
            return

        subs = db.query(models.PushSubscription).all()
        if not subs:
            print("[scheduler] nadie tiene suscripciones push registradas para escalar.")
            return

        person = day.assigned_person
        for sub in subs:
            result = send_push(
                sub,
                title="🚨 Todavía nadie le dio comida a los perros",
                body=f"Le tocaba a {person.name} y sigue sin marcarse. ¿Quién puede ir?",
                url="/",
            )
            if result == "expired":
                db.delete(sub)

        db.commit()
    finally:
        db.close()


def _get_settings_row(db) -> Optional[models.AppSettings]:
    return db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()


def _read_times() -> tuple[int, int, int, int]:
    db = SessionLocal()
    try:
        settings = _get_settings_row(db)
        if settings:
            return (
                settings.notify_hour,
                settings.notify_minute,
                settings.reminder_hour,
                settings.reminder_minute,
            )
        return 20, 0, 21, 30
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=TIMEZONE)
    notify_hour, notify_minute, reminder_hour, reminder_minute = _read_times()

    scheduler.add_job(
        check_and_notify,
        CronTrigger(hour=notify_hour, minute=notify_minute, timezone=TIMEZONE),
        id=NOTIFY_JOB_ID,
        replace_existing=True,
    )
    scheduler.add_job(
        check_and_escalate,
        CronTrigger(hour=reminder_hour, minute=reminder_minute, timezone=TIMEZONE),
        id=ESCALATE_JOB_ID,
        replace_existing=True,
    )
    scheduler.start()
    return scheduler


def reschedule(
    scheduler: BackgroundScheduler,
    notify_hour: int,
    notify_minute: int,
    reminder_hour: int,
    reminder_minute: int,
) -> None:
    """Se llama cuando alguien cambia los horarios de aviso desde Ajustes."""
    scheduler.add_job(
        check_and_notify,
        CronTrigger(hour=notify_hour, minute=notify_minute, timezone=TIMEZONE),
        id=NOTIFY_JOB_ID,
        replace_existing=True,
    )
    scheduler.add_job(
        check_and_escalate,
        CronTrigger(hour=reminder_hour, minute=reminder_minute, timezone=TIMEZONE),
        id=ESCALATE_JOB_ID,
        replace_existing=True,
    )
