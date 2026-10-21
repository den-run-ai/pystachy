# pystachy: dynamic-any
# A container whose items hold Any values (dict[str, Any], list[dict[str, Any]], ...) has the
# layout of Any's containers (#777): it becomes an Any value, and an Any value becomes one, as the
# same object, so that typed and Any code see each other's changes.
from typing import Any


def make() -> Any:
    out: dict[str, Any] = {}
    out["a"] = 1
    return out


def keys_of(table: dict[str, Any]) -> list[str]:
    return list(table)


def touch(rec: dict[str, Any]) -> None:
    rec["seen"] = True
    rec["n"] = rec.get("n", 0) + 1


def grow(xs: Any) -> None:
    xs.append({"id": 3})


flags: dict[str, dict[Any, Any]] = {"a": {"nested": {"b": 1}}}


def find(key: list[str]) -> Any:
    cont = flags
    for k in key[:-1]:
        cont = cont[k]["nested"]
    return cont.get(key[-1])


def run() -> None:
    print(make())
    doc: Any = {"a": 1, "b": [1, 2]}
    print(keys_of(doc))
    print(find(["a", "b"]))
    records: list[dict[str, Any]] = [{"id": 1}, {"id": 2, "n": 5}]
    view: Any = records
    for r in records:
        touch(r)
    grow(view)
    print(records)
    print(view is records, len(view), view[0] is records[0])
    r0: dict[str, Any] = view[0]
    r0["x"] = "y"
    print(records[0], r0 is records[0])
    names = [r["id"] for r in records]
    print(names, sum(names))
    for k, v in records[1].items():
        print(k, v)


run()
