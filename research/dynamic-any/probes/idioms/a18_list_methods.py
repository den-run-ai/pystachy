# pystachy: dynamic-any
# list methods on an Any list: append, extend, insert, index, count, reverse, sort of mixed numbers
from typing import Any

xs: Any = [3, 1.5, 2]
xs.append(True)
xs.extend([0, -1.25])
xs.insert(0, 10)
print(xs, xs.index(2), xs.count(1))
xs.sort()
print(xs)
xs.reverse()
print(xs, xs[1:3], xs[-1])
