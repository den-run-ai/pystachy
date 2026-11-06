# pystachy: dynamic-any
# The TypeError text of unsupported binary and in-place operators on Any values (compare with CPython)
from typing import Any

a: Any = 1
s: Any = "x"
n: Any = None
try:
    print(a ** s)
except TypeError as e:
    print("**:", e)
try:
    a **= s
except TypeError as e:
    print("**=:", e)
try:
    a += s
except TypeError as e:
    print("+=:", e)
try:
    n -= a
except TypeError as e:
    print("-=:", e)
try:
    a |= s
except TypeError as e:
    print("|=:", e)
