# pystachy: dynamic-any
# Slices of Any values: a str's, a list's and a tuple's items, as new values of their types, with
# steps, negative and omitted bounds and Any bounds (#782); a slice of another value raises
# CPython's TypeError.
from typing import Any

s: Any = "hello world"
xs: Any = [1, "two", 3.0, None]
t: Any = (1, 2, 3, 4, 5)
n: Any = 3
print(s[:5], s[6:], s[::-1], s[1:8:2], s[-3:], s[n:], s[:n])
print(xs[1:], xs[::-1], xs[:-1], xs[::2], xs[n:], xs[10:])
print(t[1:3], t[::-2], t[:0], t[n:], type(t[1:]).__name__)
ys = xs[:]
ys.append("new")
print(len(xs), len(ys), ys[-1])
w: Any = 5
try:
    print(w[1:])
except TypeError as err:
    print("TypeError:", err)
