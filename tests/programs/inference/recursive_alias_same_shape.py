# Two recursive aliases of the same members are one type, as CPython's are: a decoded JSON
# document is a value of a program's own alias that lists json.JSONValue's members.
import json

type Doc = None | bool | int | float | str | list[Doc] | dict[str, Doc]
type Same[G] = None | bool | int | float | str | G | list[Same[G]] | dict[str, Same[G]]
type Other = str | int | list[Other] | dict[str, Other]
type Names = int | str | list[Names] | dict[str, Names]


def depth(v: Doc) -> int:
    if isinstance(v, list):
        return 1 + max([depth(x) for x in v] + [0])
    if isinstance(v, dict):
        return 1 + max([depth(x) for x in v.values()] + [0])
    return 0


def tag(v: Doc) -> "json.JSONValue":
    return {"v": v, "depth": depth(v)}


def names(v: Other) -> list[str]:
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        out: list[str] = []
        for x in v:
            out.extend(names(x))
        return out
    return []


def main() -> None:
    doc = json.loads('{"a": [1, [2, {"b": null}]]}')
    print(depth(doc))
    mine: Doc = [1, {"k": [True, 2.5, "s"]}]
    print(json.dumps(mine), depth(mine))
    print(json.dumps(tag(doc)), tag(mine))
    both: list[Doc] = [doc, mine, json.loads("3")]
    print(both, both[0] == doc, mine == json.loads('[1, {"k": [true, 2.5, "s"]}]'))
    j: Same[float] = json.loads('{"x": [1, 2.5, null]}')
    print(j, json.dumps(j), depth(j))
    o: Other = ["x", ["y", 3], {"z": "w"}]
    n: Names = o
    print(names(o), names(n), o == n)


main()
