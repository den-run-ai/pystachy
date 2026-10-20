# An except clause naming an empty tuple of classes catches nothing (CPython tests membership in
# the tuple), also with as; isinstance() with an empty tuple is False.
try:
    raise ValueError("x")
except ():
    print("caught by ()")
except ValueError as e:
    print("ValueError", e, isinstance(e, ()))
try:
    pass
except () as e:
    pass
print("after")


def f(n: int) -> str:
    try:
        return str(10 // n)
    except () as e:
        return "never"
    except ZeroDivisionError:
        return "zero"


print(f(2), f(0))
try:
    raise KeyError("k")
except ():
    pass
