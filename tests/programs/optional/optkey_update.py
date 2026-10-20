# d[k] op= v and del d[k] look k up as d[k] does: a key that may be None raises KeyError: None,
# and past that it is a key of the dict's type (also a tuple key's item). `k in d` does not narrow
# k, but d[k] op= v stores k only where d[k] has found it, so it needs no narrowing either
from typing import Optional
import sys


def bump(d: dict[str, int], k: Optional[str]) -> int:
    if k in d:
        d[k] += 1
        return d[k]
    return -1


def look(d: dict[tuple[int, str], int], n: int, s: Optional[str]) -> int:
    t = (n, s)
    if t in d:
        d[t] += 1
        d[t] *= 2
        return d[t]
    return -1


sd = {"a": 1, "b": 2}
print(bump(sd, "a"), bump(sd, None), bump(sd, "c"), sd)
td = {(1, "a"): 10, (0, "b"): 20}
print(look(td, 1, "a"), look(td, 1, None), look(td, 0, "b"), look(td, 2, None), td)
xd: dict[int, int] = {1: 1, 2: 2}
k: Optional[int] = 2 if len(sys.argv) > 1 else None
xd[k] += 10
print(xd)
del xd[k]
s: Optional[str] = "a" if len(sys.argv) > 1 else None
del sd[s]
del td[1, s]
print(xd, sd, td)
s = None
del sd[s]
