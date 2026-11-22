# A NamedTuple field annotated float that is given an int (#1534) holds an int | float: the
# tuple's items keep their types.
from typing import NamedTuple


class V(NamedTuple):
    x: float
    y: float = 0


v = V(1)
w = V(1.5, 2)
print(v, w, v[0], w[1], v.x / 2 + w.y / 4, len(v), v == (1, 0), v == V(1.0, 0.0), hash(v) == hash((1, 0)))
x, y = w
print(x, y, list(v), v + w, v < w, max(v, w), v._replace(x=5), w._asdict())
for item in w:
    print(item, isinstance(item, int))
