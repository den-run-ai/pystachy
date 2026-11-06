# pystachy: dynamic-any
# Capture class-valued fields and globals before arguments replace their targets.
from typing import Any

EVENTS: list[str] = []


class Original:
    def __init__(self, value: int, tag: str = "default") -> None:
        EVENTS.append("original:" + tag)
        self.value = value
        self.tag = tag


class Replacement:
    def __init__(self, *, label: str) -> None:
        EVENTS.append("replacement:" + label)
        self.label = label


class Holder:
    def __init__(self) -> None:
        self.factory: Any = Original


# Establish ordinary constructors and boxed layouts before reconstructing them.
originals: list[Any] = [Original(0), Replacement(label="seed")]
holder: Any = Holder()
FACTORY: Any = type(originals[0])
EVENTS.clear()


def replace_field(value: int) -> int:
    EVENTS.append("field:" + str(value))
    holder.factory = Replacement
    return value


def replace_global(value: int) -> int:
    global FACTORY
    EVENTS.append("global:" + str(value))
    FACTORY = Replacement
    return value


def number(value: int) -> int:
    EVENTS.append("number:" + str(value))
    return value


def text(value: str) -> str:
    EVENTS.append("text:" + value)
    return value


def fails() -> int:
    EVENTS.append("argument failure")
    raise RuntimeError("argument first")


first = holder.factory(replace_field(1), tag=text("saved field"))
second = holder.factory(label="new field")
print(type(first) is Original, first.value, type(second) is Replacement)
first = FACTORY(replace_global(2))
second = FACTORY(label="new global")
print(type(first) is Original, first.value, type(second) is Replacement)
print(EVENTS)
EVENTS.clear()

# The whole failing mapping is evaluated; groups after its duplicate are not.
holder.factory = Original
try:
    holder.factory(value=replace_field(3), **{"value": number(4), "tag": text("mapping")}, later=number(5))
except TypeError as exc:
    print("merge", exc)
print(holder.factory is Replacement, EVENTS)
EVENTS.clear()

saved: Any = Original
try:
    saved(number(6), value=number(7), tag=text("binding"))
except TypeError as exc:
    print("bind", exc)
print(EVENTS)
EVENTS.clear()
try:
    saved(fails(), tag=text("not reached"), unknown=number(8))
except RuntimeError as exc:
    print("argument", exc)
print(EVENTS)
