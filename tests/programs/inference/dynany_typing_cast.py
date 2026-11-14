# pystachy: dynamic-any
# typing.cast() with Any types: a quoted type is a forward reference, as in an annotation.
import typing
from typing import Any, cast

JSONReturnType = dict[str, Any] | list[Any] | str | float | int | bool | None


def pick(n: int) -> Any:
    if n == 0:
        return [1, "a"]
    return "text"


def keys(names: list[str]) -> tuple[bool, JSONReturnType]:
    return True, cast("JSONReturnType", dict.fromkeys(names))


def main() -> None:
    w = cast("list[Any]", [1, "a"])
    w.append(None)
    v = cast("JSONReturnType", pick(0))
    u = typing.cast("JSONReturnType", pick(1))
    d = cast("dict[str, Any]", {"k": 1, "j": "s"})
    only: Any = dict.fromkeys(["x"])
    only["x"] = [1]
    print(w, v, u, d, keys(["a", "b"]), only)


main()
