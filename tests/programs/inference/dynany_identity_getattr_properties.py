# pystachy: dynamic-any
# A property return and its AttributeError fallback select the original object,
# even when the getter rebinds the numeric global used as the default.
from typing import Any

source = float("nan")
default_value = float("nan")


class Reader:
    def __init__(self, fail: bool) -> None:
        self.fail = fail

    @property
    def item(self) -> float:
        global default_value
        default_value = float("nan")
        if self.fail:
            raise AttributeError("missing")
        return source


for fail in [False, True]:
    expected: Any = default_value if fail else source
    result: Any = getattr(Reader(fail), "item", default_value)
    print("getter", fail, result is expected, len({result, expected}))


class OptionalReader:
    def __init__(self, empty: bool) -> None:
        self.empty = empty

    @property
    def item(self) -> float | None:
        return None if self.empty else source


for empty in [False, True]:
    optional_expected: Any = None if empty else source
    optional_result: Any = getattr(OptionalReader(empty), "item", None)
    print("optional", empty, optional_result is optional_expected)


integer = int("1000")


class UnionReader:
    def __init__(self, whole: bool) -> None:
        self.whole = whole

    @property
    def item(self) -> int | float:
        return integer if self.whole else source


for whole in [False, True]:
    union_expected: Any = integer if whole else source
    union_result: Any = getattr(UnionReader(whole), "item", 2.5)
    print("union", whole, union_result is union_expected)


class Exploding:
    @property
    def item(self) -> float:
        raise ValueError("propagated")


try:
    getattr(Exploding(), "item", default_value)
except ValueError as error:
    print(error)
