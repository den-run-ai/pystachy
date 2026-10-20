# error: lib_datetime_min_type.py:7: error: 'datetime.date' object has no attribute 'hour'
# datetime.min and datetime.max are datetimes typed date, as a subclass's class attribute keeps
# its base's type: narrow them with isinstance(), or write datetime(1, 1, 1) or
# datetime(9999, 12, 31, 23, 59, 59, 999999).
from datetime import datetime

print(datetime.min.hour)
