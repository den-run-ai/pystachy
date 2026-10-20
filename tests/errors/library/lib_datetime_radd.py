# error: lib_datetime_radd.py:6: error: expected timedelta, got date
# timedelta + date is date.__radd__ in CPython; reflected operators are not supported (write
# date + timedelta).
from datetime import date, timedelta

print(timedelta(days=1) + date(2024, 2, 29))
