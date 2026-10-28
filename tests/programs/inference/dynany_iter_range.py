# pystachy: dynamic-any
from typing import Any

# No explicit iter() call may mask a missing lazy range dependency.
x: Any = range(2, 9, 2)
print(list(x), list(reversed(x)), sum(x), 6 in x)
y: Any = range(5, -2, -2)
print(list(y), list(reversed(y)))
z: Any = range(0)
print(list(z), list(reversed(z)))
huge: Any = range(-9223372036854775807 - 1, 9223372036854775807)
for v in huge:
    print(v)
    break
