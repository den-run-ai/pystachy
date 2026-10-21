# pystachy: dynamic-any
# Typed code over the keys of a dict[str, Any], whose keys are boxes since it has Any's layout
# (#777): each use of a key as a str compiles, as it did, and prints what CPython prints
from typing import Any


def keys_as_str(d: dict[str, Any]) -> None:
    print(", ".join(d), "-".join(sorted(d)), "".join(d.keys()))
    print(sorted(d), max(d), min(d), list(d), [k for k in d], set(d) == {"b", "a", "c"})
    for k in d:
        print(k.upper(), k + "!", len(k), k < "b", k.startswith("a"), f"<{k}>", "%s=%r" % (k, d[k]))
    for k, v in d.items():
        s: str = k
        print(s * 2, v)
    print({k: len(k) for k in d}, {k.upper(): v for k, v in d.items()})
    print("a" in d, "z" not in d, d.get("a"), d.get("z", 0), d.pop("c"), d)


def first_key(d: dict[str, Any]) -> str:
    for k in d:
        return k
    return ""


def take(s: str) -> int:
    return len(s)


def keys_into_typed(d: dict[str, Any]) -> None:
    ks: list[str] = list(d)
    t: tuple[str, ...] = tuple(ks)
    print(ks, t, first_key(d), [take(k) for k in d], sum(take(k) for k in d))
    names = sorted(d, key=lambda k: -len(k))
    print(names, ks[0].lower(), str(list(d.keys())))
    by_len: dict[int, list[str]] = {}
    for k in d:
        by_len.setdefault(len(k), []).append(k)
    print(by_len)


def run() -> None:
    d: dict[str, Any] = {"b": 1, "a": [2], "c": {"x": 3}}
    keys_as_str(d)
    e: dict[str, Any] = {"bb": 1, "a": 2, "ccc": None}
    keys_into_typed(e)
    n: dict[str, int] = {"k": 1}
    m: dict[str, Any] = {}
    for k, v in n.items():
        m[k] = v
    m.update({"j": [1]})
    print(m, sorted(m.items()), list(m.values()))


run()
