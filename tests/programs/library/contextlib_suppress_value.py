# contextlib.suppress() kept as a value: its exception classes are class objects, which its
# __exit__ tests with issubclass(), as CPython's does
from contextlib import suppress

quiet = suppress(KeyError)
d: dict[str, int] = {}
with quiet:
    print(d["k"])
print("after")
with quiet:
    print("nothing raised")
both = suppress(KeyError, IndexError)
for i in range(3):
    with both:
        if i == 0:
            print(d["k"])
        elif i == 1:
            print([1][5])
        else:
            print("fine")
        print("not reached", i)
try:
    with quiet:
        print(int("x"))
except ValueError as e:
    print("escaped:", e)
kinds = (ValueError, KeyError)
with suppress(*kinds):
    print(int("y"))
print("after starred")
which = LookupError
with suppress(which):
    print(d["absent"])
print("after a class object")
