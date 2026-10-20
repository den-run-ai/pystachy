# error: calling class method fromisoformat() on an object of date, which may be one of datetime, is not supported: datetime overrides it
# A class method called through an object is not dispatched on the object's class: call
# date.fromisoformat() or datetime.fromisoformat().
from datetime import date

d = date(2024, 2, 29)
print(d.fromisoformat("2024-03-01"))
