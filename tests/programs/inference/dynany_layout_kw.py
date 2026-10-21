# pystachy: dynamic-any
# A dict[str, Any] that the compiler builds or reads itself (#777): a copy of **kwargs returned
# as one, format_map(), the | and |= operators, and a dataclass's field of default_factory, whose
# dict an Any view changes
from dataclasses import dataclass, field
from typing import Any


def opts(**kw: Any) -> dict[str, Any]:
    out = dict(kw)
    out["seen"] = len(kw)
    return out


def point(x: int, y: Any = None, label: str = "") -> str:
    return f"{label}({x}, {y})"


@dataclass
class Rec:
    name: str
    meta: dict[str, Any] = field(default_factory=dict)
    tags: list[Any] = field(default_factory=list)


def run() -> None:
    o = opts(a=1, b=[2], c={"d": 3})
    print(o, sorted(o), o["b"])
    view: Any = o
    view["e"] = "added"
    print(o["e"], len(o))
    d: dict[str, Any] = {"x": 1, "y": [2], "label": "p"}
    print(point(d["x"], d["y"], d["label"]))
    print("{x}/{label}".format_map(d))
    e: dict[str, Any] = {"y": None, "z": 3.5}
    print(d | e, {**d, **e} == d | e)
    d |= e
    print(d)
    r = Rec("a")
    r.meta["k"] = [1]
    r.tags.append(r.meta)
    mv: Any = r.meta
    mv["k"].append(2)
    print(r, r.tags[0] is r.meta)


run()
