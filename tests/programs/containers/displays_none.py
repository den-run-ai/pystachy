from typing import Optional


class P:
    def __repr__(self) -> str:
        return "P"


t: tuple[Optional[P], int] = (None, 1)
print(t[0], t)
xs = [None, P()]
print(xs)
q: Optional[P] = None
print(q in [None, P()])
d = {"a": None, "b": P()}
print(d)


def pair() -> tuple[Optional[P], int]:
    return (None, 2)


print(pair())
