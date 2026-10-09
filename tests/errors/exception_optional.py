# error: an exception that may be None (Exception | None) is not supported: only an object of an exception class of the program may be None
last: Exception | None = None
try:
    print(int("x"))
except ValueError as e:
    last = e
print(last)
