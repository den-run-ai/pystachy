# pystachy: dynamic-any
# A callback from another dict can clear/refill an aliased typed dict, moving its
# live key to another entry. Both the callback and the later lookup must run.
from typing import Any

victim: dict[str, int] = {}
armed: list[bool] = [False]
mode: list[int] = [0]
hashes: list[int] = [0]
equalities: list[int] = [0]
representations: list[int] = [0]


def mutate() -> None:
    victim.clear()
    victim["noise"] = 91
    victim["keep"] = 42


class Key:
    def __hash__(self) -> int:
        hashes[0] += 1
        if armed[0] and mode[0] == 0:
            mutate()
        return 7

    def __eq__(self, other: object) -> bool:
        equalities[0] += 1
        if armed[0] and mode[0] == 1:
            mutate()
        return self is other


def reset() -> None:
    armed[0] = False
    victim.clear()
    victim["keep"] = 1
    hashes[0] = 0
    equalities[0] = 0


def through_get(source: Any, key: Any, alias: dict[str, int]) -> int:
    if isinstance(source, dict):
        if "keep" in alias:
            armed[0] = True
            value = source[key]
            return alias["keep"] + int(value)
    return -1


def through_has(source: Any, key: Any, alias: dict[str, int]) -> int:
    if isinstance(source, dict):
        if "keep" in alias:
            armed[0] = True
            present = key in source
            return alias["keep"] + int(present)
    return -1


def through_set(source: Any, key: Any, alias: dict[str, int]) -> int:
    if isinstance(source, dict):
        # Separate branches preserve both membership facts for dictfuse. The
        # assignment must repeat __hash__/__eq__, even though key is present.
        if key in source:
            if "keep" in alias:
                armed[0] = True
                source[key] = 5
                return alias["keep"]
    return -1


key = Key()
other = Key()
source: Any = {other: 3, key: 5}
for m in [0, 1]:
    mode[0] = m
    reset()
    print("get", m, through_get(source, key, victim), hashes[0], equalities[0])
    reset()
    print("has", m, through_has(source, key, victim), hashes[0], equalities[0])
    reset()
    print("set", m, through_set(source, key, victim), hashes[0], equalities[0])


class Shown:
    def __repr__(self) -> str:
        representations[0] += 1
        mutate()
        return "shown"


def shown_hit(table: dict[Shown, int], key: Shown) -> int:
    if key in table:
        return table[key]
    return -1


def shown_miss(table: dict[Shown, int], key: Shown) -> None:
    if "keep" in victim:
        try:
            print(table[key])
        except KeyError as exc:
            print("repr", str(exc))
        print("repr victim", victim["keep"], representations[0])


reset()
shown = Shown()
print("repr hit", shown_hit({shown: 9}, shown), victim["keep"], representations[0])
shown_miss({}, shown)
