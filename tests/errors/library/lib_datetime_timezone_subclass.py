# error: lib_datetime_timezone_subclass.py:7: error: a base that defines __init_subclass__ is not supported (CPython calls timezone.__init_subclass__() when it creates class Zone)
# CPython raises TypeError: type 'datetime.timezone' is not an acceptable base type; subclass
# tzinfo for other time zones.
from datetime import timedelta, timezone


class Zone(timezone):
    pass


print(Zone(timedelta(0)))
