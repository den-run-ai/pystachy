# error: '_R' would be None, which Pystachy binds no type variable to (a list or dict of None values has no type)
from functools import cache

seen: list[int] = []


@cache
def visit(x: int) -> None:
    seen.append(x)


visit(1)
visit(1)
print(seen)
