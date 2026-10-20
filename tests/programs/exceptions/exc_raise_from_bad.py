# raise ... from a cause that is not an exception (nor None) raises TypeError where it runs, as
# CPython does, after the exception and the cause are evaluated: a handler can catch it.
def f(x: int) -> None:
    raise ValueError("x") from x


try:
    raise ValueError("x") from 5
except TypeError as e:
    print("caught", e)
try:
    f(3)
except TypeError as e:
    print("caught", e)
print("end")
raise KeyError("k") from "s"
