# pystachy: dynamic-any
# A local that may be unassigned keeps an "is assigned" flag slot under its own slot's number,
# beside its numeric identity companions. The exact-payload guard proof (PYSTACHY_IRCHECK=1)
# must name each slot as lowering does, or the flag hides the local's own type.
from typing import Any


def maybe_float(value: Any, flag: bool) -> float:
    if flag:
        x = 1.5
    if isinstance(value, float):
        return value + 1.0
    if flag:
        return x
    return 0.0


def maybe_held(value: Any, other: Any, flag: bool) -> float:
    if flag:
        held: Any = other
    if isinstance(value, float):
        return value + 1.0
    if flag and isinstance(held, float):
        return held + 2.0
    return 0.0


def maybe_word(value: Any, flag: bool) -> str:
    if flag:
        word: Any = value
    if flag and isinstance(word, str):
        return word + "!"
    return "-"


print(maybe_float(2.0, True), maybe_float("s", True), maybe_float("s", False))
print(maybe_held(2.0, 0.5, True), maybe_held("s", 0.5, True), maybe_held("s", 0.5, False), maybe_held("s", "t", True))
print(maybe_word("a", True), maybe_word("a", False), maybe_word(3, True))
