# pystachy: dynamic-any
# A display stored into an Any value's item or attribute holds Any values, as a CPython container
# does whatever is stored into it later (#777): an empty one too, and one of typed items, also
# where the Any value is what a call returns, a conditional expression's value or a tuple's item
from typing import Any


class Node:
    def __init__(self) -> None:
        self.kids: Any = None


cont: Any = {}
cont["k"] = {}
cont["k"]["x"] = 1
cont["l"] = []
cont["l"].append(1)
cont["l"].append("two")
cont["t"] = [1, 2]
cont["t"].append("three")
cont["m"] = {"a": 1}
cont["m"]["b"] = [None]
cont["n"] = [{}]
cont["n"][0]["deep"] = []
cont["n"][0]["deep"].append({"z": 0.5})
print(cont)

inner = cont["k"]
inner["y"] = 2
print(cont["k"], inner is cont["k"])

lst: Any = [None, None]
lst[0] = {}
lst[1] = [1]
lst[0]["s"] = "v"
lst[1].append(2.5)
print(lst)

o: Any = Node()
o.kids = []
o.kids.append(Node())
o.kids[0].kids = {"leaf": True}
print(len(o.kids), o.kids[0].kids)


def put(c: Any, k: str) -> None:
    c[k] = {"n": [k]}
    c[k]["n"].append(len(k))


put(cont, "f")
cont["p"], cont["q"] = [], {}
cont["sq"] = [i * i for i in range(3)]
cont["sq"].append("x")
cont["l"] += [3]
print(cont["f"], cont["p"], cont["q"], cont["sq"], cont["l"])


def get() -> Any:
    return cont


def node() -> Any:
    return o


get()["g"] = {}
get()["g"]["h"] = [1, 2]
node().kids = [{}]
node().kids[0]["leaf"] = False
o.kids[0]["more"] = [None]
(cont if len(cont) > 0 else lst)["c"] = []
print(cont["g"], o.kids, cont["c"])

pair = (len(cont), lst)
pair[1][0]["u"] = {}
pair[1][0]["u"]["w"] = [len(pair)]
print(lst[0], pair[0] > 0)


class Holder:
    def __init__(self) -> None:
        self.d: Any = {}

    def get(self) -> Any:
        return self.d


h = Holder()
h.get()["m"] = {}
h.get()["m"]["n"] = [2.5]
fns: Any = [get]
fns[0]()["fn"] = []
print(h.d, cont["fn"])
