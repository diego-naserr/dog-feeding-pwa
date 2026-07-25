"""
Configuración editable de la app. Para cambiar quién le toca cada día,
o agregar/quitar personas, solo hay que editar PEOPLE y WEEKDAY_SCHEDULE.
No hace falta tocar el resto del código.
"""
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/Santiago")

# Lista de personas activas (deben coincidir con los nombres usados abajo)
PEOPLE = ["Diego", "Tomás", "Ignacia", "Fran"]

# date.weekday(): 0=Lunes, 1=Martes, 2=Miércoles, 3=Jueves, 4=Viernes, 5=Sábado, 6=Domingo
WEEKDAY_SCHEDULE = {
    0: "Diego",     # Lunes
    1: "Tomás",     # Martes
    2: "Diego",     # Miércoles
    3: "Ignacia",   # Jueves
    4: "Tomás",     # Viernes
    5: "Fran",      # Sábado
    6: "Ignacia",   # Domingo
}

# Hora del aviso push (hora de Chile)
NOTIFY_HOUR = 20
NOTIFY_MINUTE = 0

# Hora límite para considerar la comida "a tiempo" (da un margen después del
# aviso antes de marcarlo como tarde). Después de esta hora, "tarde".
ON_TIME_CUTOFF_HOUR = 21
ON_TIME_CUTOFF_MINUTE = 0
