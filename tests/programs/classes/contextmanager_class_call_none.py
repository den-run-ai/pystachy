from contextlib import contextmanager
from typing import Iterator


class Scope:
    def __init__(self) -> None:
        self.value = 8

    @contextmanager
    def opened(self, x: int, *, extra: int = 0) -> Iterator[int]:
        print("base enter", self is None)
        try:
            yield x + extra
        finally:
            print("base exit")

    @contextmanager
    def read(self, x: int) -> Iterator[int]:
        print("read enter", x)
        yield self.value


class Child(Scope):
    @contextmanager
    def opened(self, x: int, *, extra: int = 0) -> Iterator[int]:
        print("child enter", self is None)
        try:
            yield x + extra + 100
        finally:
            print("child exit")


def receiver(present: bool) -> Scope | None:
    print("receiver", present)
    return Child() if present else None


def child_receiver() -> Child | None:
    return None


def argument(x: int) -> int:
    print("argument", x)
    return x


for present in [False, True]:
    try:
        manager = Scope.opened(receiver(present), argument(2), extra=argument(3))
        print("created")
        with manager as result:
            print("result", result)
    except AttributeError as error:
        print("unexpected", str(error))
    try:
        manager_read = Scope.read(receiver(present), argument(4))
        print("read created")
        with manager_read as result:
            print("read result", result)
    except AttributeError as error:
        print("read error", str(error))


try:
    with Child.opened(child_receiver(), argument(6)) as result:
        print("child result", result)
except AttributeError as error:
    print("unexpected", str(error))


# Recreation must keep the explicitly selected base generator on a child object.
@Scope.opened(receiver(True), argument(7), extra=argument(8))
def decorated(x: int) -> int:
    print("decorated", x)
    return x + 1


print(decorated(1), decorated(2))


def nullable_decorator() -> None:
    @Scope.opened(receiver(False), argument(9))
    def inner(x: int) -> int:
        print("inner", x)
        return x

    print(inner(3), inner(4))


try:
    nullable_decorator()
except AttributeError as error:
    print("unexpected", str(error))


def nullable_child_decorator() -> None:
    @Child.opened(child_receiver(), argument(10))
    def inner() -> int:
        return 11

    print("child decorated", inner(), inner())


try:
    nullable_child_decorator()
except AttributeError as error:
    print("unexpected", str(error))


# The factory keeps the original object, while later mutations remain visible.
original = Scope()
saved = Scope.read(original, argument(12))
original.value = 19
original = Scope()
with saved as result:
    print("saved receiver", result)


class _pys_cm_factory:
    @contextmanager
    def opened(_pys_cm_factory_: "_pys_cm_factory") -> Iterator[int]:
        yield 23


with _pys_cm_factory().opened() as result:
    print("factory name", result)
