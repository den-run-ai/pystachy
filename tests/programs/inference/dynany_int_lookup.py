# pystachy: dynamic-any
# Integer queries may inspect boxed-key tables without boxing the query. A matching
# non-integer key must fall back before callbacks, using the original integer object.
from typing import Any


def pure_keys() -> None:
    keys = [-9223372036854775808, -2305843009213693952, -2, -1, 0, 1,
            1000, 2305843009213693951, 2305843009213693952, 9223372036854775807]
    d: dict[int, Any] = {}
    for k in keys:
        d[k] = str(k)
    print("integers", len(d))
    for k in keys:
        print(k, k in d, d[k], d.get(k, "missing"))
    print("miss", 1234 in d, 1234 not in d, d.get(1234, "missing"))
    try:
        print(d[1234])
    except KeyError as error:
        print("missing key", str(error))

    # The canonical table remains shared when an Any alias inserts another key type.
    alias: Any = d
    alias[False] = "false"
    alias[True] = "true"
    print("bool", d[0], d[1], False in d, True in d)
    alias[1001.0] = "float"
    print("float", 1001 in d, d[1001], d.get(1001))
    alias["unrelated"] = "string"
    print("mixed", d[1000], 1234 in d)

    # Tombstones, resize, copy and clear must not change lookup interpretation.
    for k in keys[::2]:
        del d[k]
    for k in range(40):
        d[k + 4000] = k
    copied = d.copy()
    print("resized", len(copied), copied[4003], 4004 in copied, copied.get(5000))
    copied.clear()
    print("clear", 4003 in copied, copied.get(4003, "empty"))


events: list[str] = []
captured: list[Any] = []
active: dict[int, Any] = {}


class Key:
    def __init__(self, value: int, action: str) -> None:
        self.value = value
        self.action = action

    def __hash__(self) -> int:
        return self.value

    def __eq__(self, other: Any) -> bool:
        events.append("eq")
        captured.append(other)
        action = self.action
        self.action = ""
        if action == "replace":
            active.clear()
            active[self.value] = "replaced"
        elif action == "raise":
            raise ValueError("comparison")
        return other == self.value


def receiver() -> dict[int, Any]:
    events.append("receiver")
    return active


def query() -> int:
    events.append("query")
    return int("1000")


def default() -> Any:
    events.append("default")
    return "default"


def callback_keys() -> None:
    global active
    k = int("1000")
    active = {}
    alias: Any = active
    alias[Key(k, "")] = "custom"
    events.clear()
    captured.clear()
    print("callback", k in active, active[k], active.get(k, "missing"))
    print("captured", len(captured), captured[0] is k, captured[1] is k, captured[2] is k)
    print("callbacks", events)
    # Keep the observed query alive after temporary objects are discarded. Program
    # GC-stress runs collect at every allocation, including these list allocations.
    for i in range(40):
        temporary: Any = [i, str(i)]
    print("retained", captured[0] is k, captured[0] is captured[2], len(temporary))

    # The probe may pass a pure integer collision before reaching the callback.
    active = {2305843009213694951: "collision"}
    alias = active
    alias[Key(k, "")] = "custom"
    events.clear()
    captured.clear()
    print("collision fallback", active[k], events, captured[0] is k)

    events.clear()
    print("order getitem", receiver()[query()])
    print(events)
    events.clear()
    print("order get", receiver().get(query(), default()))
    print(events)
    events.clear()
    print("order has", query() in receiver())
    print(events)

    active = {}
    alias = active
    alias[Key(k, "replace")] = "old"
    events.clear()
    captured.clear()
    print("restart", active[k], active[k], len(active), events)
    print("restart identity", captured[0] is k)

    active = {}
    alias = active
    alias[Key(k, "raise")] = "old"
    events.clear()
    captured.clear()
    try:
        print(active[k])
    except ValueError as error:
        print("exception", str(error), events, captured[0] is k)


pure_keys()
callback_keys()
