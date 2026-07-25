"""
Valores iniciales, usados solo la primera vez que arranca la app (para
sembrar la base de datos vacía). Después de eso, todo esto se edita desde
la pestaña Ajustes de la app — cambiar este archivo ya no tiene efecto en
una instalación que ya arrancó antes.

Si estás por desplegar por primera vez, podés dejar estos valores como
punto de partida; después ajustás personas, rotación y hora del aviso
directamente desde el celular.
"""
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/Santiago")

# Personas con las que arranca la app la primera vez.
PEOPLE = ["Diego", "Tomás", "Ignacia", "Fran"]

# Rotación inicial. date.weekday(): 0=Lunes ... 6=Domingo
WEEKDAY_SCHEDULE = {
    0: "Diego",     # Lunes
    1: "Tomás",     # Martes
    2: "Diego",     # Miércoles
    3: "Ignacia",   # Jueves
    4: "Tomás",     # Viernes
    5: "Fran",      # Sábado
    6: "Ignacia",   # Domingo
}

# Hora inicial del aviso push (hora de Chile). La hora "a tiempo" se
# calcula automáticamente como una hora después de esta.
NOTIFY_HOUR = 20
NOTIFY_MINUTE = 0
