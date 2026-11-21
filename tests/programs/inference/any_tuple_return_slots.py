from __future__ import annotations

from typing import Any, Tuple as Pair
from tuple_entries import DEFAULT_ENTRY, State, default


def entry(flag: bool, value: Any, state: State) -> Pair[State | None, Any]:
    if flag:
        return None, value
    return state, value


def seen(flag: bool, token: Any) -> None:
    state = State("ready")
    got, value = entry(flag, token, state)
    print(got is state, got.name if got is not None else "absent", value is token)


seen(False, ["x"])
seen(True, State("token"))


def concrete(x: Any) -> tuple[int | None, Any]:
    return 1, x


print(concrete("tag")[0] + 2)


print(default(True, "x") is default(True, "y"))
print(default(True, "x") is DEFAULT_ENTRY)


def already_joined(flag: bool, state: State, token: Any) -> tuple[State | None, Any]:
    if flag:
        return state, "ok"
    return state, token


print(already_joined(False, State("x"), 3)[1])
