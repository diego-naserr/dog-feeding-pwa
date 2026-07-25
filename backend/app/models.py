from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from .database import Base


class Person(Base):
    __tablename__ = "people"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    color = Column(String, nullable=True)


class FeedingDay(Base):
    """Un registro por fecha calendario. assigned_person_id queda congelado
    al crearse el registro, para no reescribir el historial si la rotación
    de config.py cambia más adelante."""

    __tablename__ = "feeding_days"

    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True, nullable=False)
    assigned_person_id = Column(Integer, ForeignKey("people.id"), nullable=False)
    fed = Column(Boolean, default=False, nullable=False)
    fed_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True)
    fed_at = Column(DateTime, nullable=True)
    notified_at = Column(DateTime, nullable=True)

    assigned_person = relationship("Person", foreign_keys=[assigned_person_id])
    fed_by_person = relationship("Person", foreign_keys=[fed_by_person_id])


class WeekdaySchedule(Base):
    """Quien tiene asignado cada dia de la semana. Editable desde Ajustes;
    se siembra una vez desde config.WEEKDAY_SCHEDULE en la primera version
    que la introduce, y desde ahi vive solo en la base de datos."""

    __tablename__ = "weekday_schedule"

    weekday = Column(Integer, primary_key=True)  # 0=Lunes ... 6=Domingo
    person_id = Column(Integer, ForeignKey("people.id"), nullable=False)

    person = relationship("Person")


class AppSettings(Base):
    """Fila unica (id=1) con ajustes editables desde la app."""

    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True)
    notify_hour = Column(Integer, nullable=False, default=20)
    notify_minute = Column(Integer, nullable=False, default=0)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("people.id"), nullable=False)
    endpoint = Column(String, unique=True, nullable=False)
    p256dh = Column(String, nullable=False)
    auth = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)

    person = relationship("Person")
