# == and != between a complex | None and an optional union holding a complex number: None,
# held by either side, equals only None, by identity as CPython compares them
from typing import Optional


def get(flag: bool) -> complex | None:
    return 1j if flag else None


def pick(k: int) -> Optional[int | complex]:
    return None if k == 0 else (1 if k == 1 else 2j)


x = get(False)
y = get(True)
for k in range(3):
    u = pick(k)
    print(x == u, u == x, y == u, u != y, u == None, x != u)
