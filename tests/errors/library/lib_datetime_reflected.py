# error: lib_datetime_reflected.py:6: error: reflected operator methods are not supported (int * timedelta calls timedelta.__rmul__)
# CPython calls timedelta.__rmul__ for int * timedelta; reflected operators are not supported
# (write timedelta * int).
from datetime import timedelta

print(2 * timedelta(days=1))
