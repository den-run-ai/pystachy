# Documented port limitation: method managers expose a bound-generator func typed by
# the hierarchy's root. A None receiver has no dynamic tag, so its inspected name is
# the root's static metadata even for an explicit derived-class call. CPython exposes
# the original unbound generator and prints Child.scope. Execution retains Child's body.
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


def absent() -> Child | None:
    return None


manager = Child.scope(absent())
print(manager.func.__name__, manager.func.__qualname__)
with manager as result:
    print(result)
