from contextlib import contextmanager
from typing import Iterator

class Base:
    @contextmanager
    def scope(self) -> Iterator[int]:
        yield 1

class Child(Base):
    @contextmanager
    def scope(self) -> Iterator[int]:
        yield 2

def absent() -> Base | None:
    return None

manager = Base.scope(absent())
print(manager.func.__name__)
print(manager.func.__qualname__)

# Aliasing func must not turn metadata inspection into a receiver dereference.
function = manager.func
print(function.__name__, function.__qualname__)
for present in [False, True]:
    value: Base | None = Child() if present else None
    selected = Base.scope(value)
    print(selected.func.__name__)
    if value is None:
        print(selected.func.__qualname__)
    with selected as result:
        print(result)

# Existing ordinary bound-method metadata still selects the receiver's override.
child = Child()
print(child.scope.__name__, child.scope.__qualname__)
