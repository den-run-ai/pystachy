# CPython calls timedelta.__rmul__ for int * timedelta and float * timedelta: a number has no
# method for a timedelta.
from datetime import timedelta

print(2 * timedelta(days=1))
print(1.5 * timedelta(hours=2), 3 * timedelta(minutes=20) == timedelta(hours=1))
