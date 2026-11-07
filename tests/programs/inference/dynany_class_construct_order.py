# pystachy: dynamic-any
# Capture a class before argument effects, then bind arguments and initialize.
from typing import Any

EVENTS: list[str] = []
FACTORIES: dict[str, Any] = {}


class Original:
    def __init__(self, value: int) -> None:
        EVENTS.append("original")
        self.value = value


class Replacement:
    def __init__(self, value: int) -> None:
        EVENTS.append("replacement")
        self.value = value


class Fails:
    def __init__(self, value: int) -> None:
        EVENTS.append("initializer")
        if value < 0:
            raise ValueError("failed init")
        self.value = value


def argument() -> int:
    EVENTS.append("argument")
    FACTORIES["item"] = Replacement
    return 7


def bad_argument() -> int:
    EVENTS.append("bad argument")
    raise ValueError("failed argument")


# The program already carries each ordinary instance layout through Any.
originals: list[Any] = [Original(0), Replacement(0), Fails(0)]
EVENTS.clear()
FACTORIES["item"] = Original
value = FACTORIES["item"](argument())
print(type(value) is Original, value.value, EVENTS)
value = FACTORIES["item"](8)
print(type(value) is Replacement, value.value, EVENTS)

try:
    FACTORIES["missing"](argument())
except KeyError:
    print("missing before argument", EVENTS)
try:
    FACTORIES["item"](argument(), argument())
except TypeError:
    print("arguments before arity", EVENTS)
try:
    FACTORIES["item"](unknown=argument())
except TypeError:
    print("argument before keyword", EVENTS)
try:
    FACTORIES["item"](bad_argument())
except ValueError as exc:
    print(str(exc), EVENTS)

fails: Any = Fails
try:
    fails(-argument())
except ValueError as exc:
    print(str(exc), EVENTS)
