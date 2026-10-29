# pystachy: dynamic-any
# A module that opts in, imported by programs that do not (dynany_identity_scope*.py): its code
# tracks numeric identity, theirs only where a value crosses into it
# (docs/dynamic-any.md#identity-scope).
from typing import Any, Callable

kept: list[Any] = []


def keep(x: Any) -> None:
    kept.append(x)


def kept_same() -> str:
    return f"{kept[0] is kept[1]} {kept[1] is kept[0]} {kept[0] == kept[1]}"


def table(text: str) -> dict[str, Any]:
    # n is one object, which two items hold; int(text) makes another
    n = int(text)
    return {"a": n, "b": n, "c": int(text), "s": text}


def same(a: Any, b: Any) -> bool:
    return a is b


def fields(p: Any, x: Any) -> str:
    return f"{p.n is p.n} {p.n is x} {x is p.n} {p.m is p.n} {p.n is p.k} {p.n == p.k}"


def call(f: Callable[[str], Any], text: str) -> Any:
    return f(text)
