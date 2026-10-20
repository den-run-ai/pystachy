# error: type(x).__name__ of Generator[str] is not supported
# itertools' functions return generators (lib/compatibility.md), whose class name CPython's
# islice object does not have
from itertools import islice

print(type(islice("abc", 2)).__name__)
