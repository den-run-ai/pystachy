# pystachy: dynamic-any
# a value of object that holds an Any list, tuple or dict narrows by isinstance() to the view of it
# that a typed container's narrows to: its operations are the Any container's own, and it stays
# the container that the Any value is, which a change through that value shows
from typing import Any


def main() -> None:
    a: Any = [1, "x", [2]]
    o: object = a
    if isinstance(o, list):
        print(len(o), o[0], o[2], 1 in o, "x" in o, 9 in o, o.index("x"), o.count(1), o is a)
        for i in o:
            print("item", i)
        a.append(5)
        print(len(o), o[-1], o)
    d: Any = {"k": 1, 2: "two"}
    od: object = d
    if isinstance(od, dict):
        print(od["k"], od[2], od[2.0], od.get("zz"), "k" in od, len(od))
        for k in od:
            print("key", k)
        for k, v in od.items():
            print("pair", k, v)
        try:
            print(od["missing"])
        except KeyError as e:
            print("KeyError", e)
    t: Any = (1, 2)
    ot: object = t
    if isinstance(ot, tuple):
        print(len(ot), ot[1], ot)
        for i in ot:
            print("titem", i)


main()
