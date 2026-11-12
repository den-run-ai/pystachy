class _empty:
    """Marker."""


class P:
    def __init__(self, name: str, default: type[object] = _empty) -> None:
        self.name = name
        self.default = default


EMPTY: type[object] = _empty
p = P("x")
print(p.default is _empty, p.default is EMPTY, p.default)
q = P("y", P)
print(q.default is _empty, q.default is P)
d: type[object] = _empty
print(d is _empty)
d = P
print(d is _empty)
