# error: importing module '_strptime' in a function of module 'datetime' is not supported
# datetime.strptime() needs CPython's _strptime, which needs the locale and calendar modules;
# lib/datetime.py does not provide it.
from datetime import datetime

print(datetime.strptime("2024-02-29", "%Y-%m-%d"))
