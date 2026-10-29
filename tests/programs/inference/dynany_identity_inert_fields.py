# pystachy: dynamic-any
from typing import Any
import inert_scope

cursor = inert_scope.make("x" * 1000)
a: Any = cursor.pos
b: Any = cursor.pos
print(a is b)
number = int("2000")
cursor.pos = number
c: Any = cursor.pos
d: Any = number
print(c is d, a is c)
print(getattr(cursor, "pos"), dict(vars(cursor)))
