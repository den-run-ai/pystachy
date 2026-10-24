# pystachy: dynamic-any
from typing import Any

x: Any = float("nan")
y: Any = float("nan")
xs: list[float] = [x, x, y]
a: Any = xs[0]
b: Any = xs[1]
print("original", a is x, b is x, a is b)
print("nan cardinality", len({a, b, xs[0], xs[2]}))
print("search", x in xs, y in xs, xs.count(x), xs.index(y))
copy = xs.copy()
print("copy", copy == xs, copy <= xs, copy[0] is x)
copy.reverse()
print("reverse", copy[0] is y, copy[2] is x)
copy[0] = x
copy.append(y)
copy.insert(1, y)
print("mutate", copy[0] is x, copy[1] is y, copy[-1] is y)
print("pop", copy.pop() is y)
copy.remove(y)
print("remove", len(copy), copy.count(y))
print("select", min(xs) is x, max(xs) is x)
seen: set[Any] = {v for v in xs}
print("iteration", len(seen))
