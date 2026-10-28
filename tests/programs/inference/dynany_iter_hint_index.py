# pystachy: dynamic-any
from typing import Any


class BadIndex:
    def __index__(self, extra: int) -> int:
        print("unreachable bad index")
        return extra


class GoodIndex:
    def __index__(self) -> int:
        print("good index")
        return 2


class OtherIndex:
    def __index__(self) -> int:
        print("other index")
        return 3


class DynamicHint:
    def __init__(self, value: Any) -> None:
        self.value = value

    def __iter__(self):
        print("dynamic next")
        yield 1

    def __len__(self):
        print("dynamic hint")
        return self.value


# The first call must not compile the unrelated BadIndex arm as an invalid call.
unrelated: Any = BadIndex()
for value in [0, unrelated, GoodIndex()]:
    source: Any = DynamicHint(value)
    print("dynamic", list(source))


class StaticBadHint:
    def __iter__(self):
        print("static next")
        yield 4

    def __len__(self):
        print("static hint")
        return BadIndex()


source = StaticBadHint()
print("static", list(source))


def union_hint(n: int) -> GoodIndex | OtherIndex:
    if n == 0:
        return None
    if n == 1:
        return GoodIndex()
    return OtherIndex()


class UnionHint:
    def __init__(self, n: int) -> None:
        self.n = n

    def __iter__(self):
        print("union next")
        yield 2

    def __len__(self):
        print("union hint")
        return union_hint(self.n)


for n in range(3):
    source = UnionHint(n)
    print("union", list(source))


def nullable_hint(valid: bool) -> GoodIndex:
    return GoodIndex() if valid else None


class NullableHint:
    def __init__(self, valid: bool) -> None:
        self.valid = valid

    def __iter__(self):
        yield 3

    def __len__(self):
        print("nullable hint")
        return nullable_hint(self.valid)


for valid in [False, True]:
    source = NullableHint(valid)
    print("nullable", list(source))
