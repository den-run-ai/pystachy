# pystachy: dynamic-any
# Error names run user __str__ only when an unpacking or merge actually fails.
from typing import Any

EVENTS: list[str] = []


class Call:
    def __call__(self, value: int = 0) -> int:
        EVENTS.append("call")
        return value

    def __str__(self) -> str:
        EVENTS.append("callee str")
        return "CALL"


class Broken:
    def __call__(self, value: int = 0) -> int:
        return value

    def __str__(self) -> str:
        EVENTS.append("broken str")
        raise ValueError("name failed")


class Key:
    def __hash__(self) -> int:
        return 41

    def __eq__(self, other: "Key") -> bool:
        return self is other

    def __str__(self) -> str:
        EVENTS.append("key str")
        return "KEY"


class BrokenKey:
    def __hash__(self) -> int:
        return 42

    def __eq__(self, other: "BrokenKey") -> bool:
        return self is other

    def __str__(self) -> str:
        EVENTS.append("broken key str")
        raise ValueError("key name failed")


def note(label: str, value: Any) -> Any:
    EVENTS.append(label)
    return value


call: Any = Call()
broken: Any = Broken()
key: Any = Key()
broken_key: Any = BrokenKey()
for case in range(9):
    EVENTS.clear()
    try:
        if case == 0:
            print("returned", call(*note("args", [3]), **note("kwargs", {})))
        elif case == 1:
            call(*note("args", 7), value=note("keyword", 4))
        elif case == 2:
            call(*note("args", []), **note("first", {"value": 1}), **note("second", {"value": 2}), ignored=note("last", 3))
        elif case == 3:
            call(*note("args", []), **note("first", {key: 1}), **note("second", {key: 2}), ignored=note("last", 3))
        elif case == 4:
            broken(*note("args", 7), value=note("keyword", 4))
        elif case == 5:
            broken(*note("args", []), **note("first", {"value": 1}), **note("second", {"value": 2}))
        elif case == 6:
            call(*note("args", []), **note("first", {broken_key: 1}), **note("second", {broken_key: 2}))
        elif case == 7:
            call(*note("args", []), **note("not mapping", 7))
        else:
            call(*note("args", []), **note("keys", {key: 1}), ignored=note("last", 3))
    except (TypeError, ValueError) as error:
        print(case, type(error).__name__, str(error))
    print(EVENTS)
