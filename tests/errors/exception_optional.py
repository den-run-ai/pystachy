# error: an exception that may be None (Exception | None) is not supported: only class types can be optional
last: Exception | None = None
try:
    print(int("x"))
except ValueError as e:
    last = e
print(last)
