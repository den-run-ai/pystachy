# pystachy: dynamic-any
# json.loads() into Any values and json.dumps() of them nest as deep as CPython's C decoder and
# encoder do, whatever the recursion limit: 9,998 containers (and, encoding, default() conversions
# in progress), of which those past the first 64 are decoded and encoded without a call for each.
# What loads() returns, the errors past the bounds and the positions of errors in deep text are
# CPython's, as are tuples, keys of every kind, skipkeys, sort_keys, default() and what it changes,
# and circular references at any depth.
import json
import sys
from typing import Any


def depth_of(value: Any) -> int:
    n = 0
    while True:
        if isinstance(value, list) and len(value) > 0:
            value = value[0]
        elif isinstance(value, dict) and len(value) > 0:
            value = value["a"]
        else:
            return n
        n += 1


def probe(source: str) -> str:
    try:
        value: Any = json.loads(source)
        return "depth %d %s" % (depth_of(value), json.dumps(value)[-14:] if len(source) < 700 else "")
    except RecursionError as exc:
        return str(exc)
    except json.JSONDecodeError as exc:
        return "JSONDecodeError " + str(exc)


def decoding() -> None:
    for n in (1, 63, 64, 65, 66, 130, 600):
        print(n, probe("[" * n + "0" + "]" * n), "|", probe('{"a":' * n + "0" + "}" * n), "|",
              probe('[{"a":' * (n // 2) + "[0]" + "}]" * (n // 2)))
    # (the bound, once for each kind of container: a test that also runs with a collection at
    # every allocation cannot afford more of these)
    print(probe("[" * 9998 + "0" + "]" * 9998))
    print(probe('{"a":' * 9999 + "0" + "}" * 9999))
    print(probe('[{"a":' * 4999 + "[0]" + "}]" * 4999))
    for n in (63, 64, 65, 70, 300):
        opened = "[" * n
        print(n, probe(opened + "1" + "]" * (n - 1)))
        print(n, probe(opened + "1,]" + "]" * (n - 1)))
        print(n, probe(opened + "1 2" + "]" * n))
        print(n, probe(opened + "" + "]" * n + "]"))
        print(n, probe(opened + '{"a" 1}' + "]" * n))
        print(n, probe(opened + '{a: 1}' + "]" * n))
        print(n, probe(opened + '{"a": 1,}' + "]" * n))
        print(n, probe(opened + '{"a": }' + "]" * n))
        print(n, probe(opened + '[1, "x", null, true, -2.5e3, {"a": [], "b": {}}, [[]]]' + "]" * n))
        print(n, probe('{"a":' * n + '{"a": {"b": 1, "a": [1, {"a": "deep"}], "c": 2}, "z": 9}' + "}" * n))
        print(n, probe('{"a":' * n + '1' + "}" * (n - 1)))
        print(n, probe('{"a":' * n + '1' + "}" * n + "}"))
    # (a document's items keep their order and its duplicate keys their last value, at any depth)
    wide = "[" * 80 + '{"k": 1, "j": [1, 2, {"k": 3}], "k": 2}, [3, 4], "s"' + "]" * 80
    value: Any = json.loads(wide)
    for _ in range(79):
        if isinstance(value, list):
            value = value[0]
    print(json.dumps(value))
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(160)
    print("low limit", probe("[" * 2001 + "0" + "]" * 2001))
    sys.setrecursionlimit(limit)


class Obj:
    def __init__(self, v: Any) -> None:
        self.v = v


class Chain:
    def __init__(self, n: int, last: Any = 7) -> None:
        self.n = n
        self.last = last


class Loop:
    pass


class Turn:
    def __init__(self) -> None:
        self.n = 0
        self.last: Any = 0


def default(o: Any) -> Any:
    if isinstance(o, Chain):
        return Chain(o.n - 1, o.last) if o.n > 0 else o.last
    if isinstance(o, Obj):
        return o.v
    if isinstance(o, Loop):
        return o
    raise TypeError("default() cannot convert " + type(o).__name__)


# A list that holds a value which default() converts to that list again, n times, and then to
# its last value: where circular references are not looked for, n + 1 conversions in progress
# and as many lists around them, of two objects.
turn = Turn()
ring: list[Any] = [turn]


def spin(n: int, last: Any) -> Any:
    turn.n = n
    turn.last = last
    return ring


def unroll(o: Any) -> Any:
    if o is turn:
        if turn.n == 0:
            return turn.last
        turn.n -= 1
        return ring
    return default(o)


def wrap(value: Any, n: int, kind: int) -> Any:
    for i in range(n):
        if kind == 0:
            value = [value]
        elif kind == 1:
            value = {"w": value}
        elif kind == 2:
            value = (value,)
        elif i % 3 == 0:
            value = [i, value, "t"]
        elif i % 3 == 1:
            value = {"p": i, "w": value, 3: None}
        else:
            value = (value, i)
    return value


def brief(text: str) -> str:
    return text if len(text) < 150 else text[:40] + " ... " + text[-60:]


def run(label: str, value: Any, skipkeys: bool = False, ensure_ascii: bool = True, check_circular: bool = True,
        allow_nan: bool = True, indent: Any = None, compact: bool = False, fn: Any = None,
        sort_keys: bool = False) -> None:
    try:
        if compact:
            text = json.dumps(value, skipkeys=skipkeys, ensure_ascii=ensure_ascii, check_circular=check_circular,
                              allow_nan=allow_nan, indent=indent, separators=(",", ":"), default=fn,
                              sort_keys=sort_keys)
        else:
            text = json.dumps(value, skipkeys=skipkeys, ensure_ascii=ensure_ascii, check_circular=check_circular,
                              allow_nan=allow_nan, indent=indent, default=fn, sort_keys=sort_keys)
        print(label, len(text), brief(text))
    except (RecursionError, ValueError, TypeError) as exc:
        print(label, type(exc).__name__, exc)


def payload() -> Any:
    return [1, "x", None, True, False, 2.5, -0.0, {"k": [], "j": {}, "t": (), "é": " \U0001f600"}, (1, (2, [3]))]


def keyed() -> Any:
    return {2: "a", 2.5: "b", False: "c", None: "d", "s": {"z": 1, "y": [2, {"b": 1, "a": 2}]}, 10: [], -1: {}}


live: dict[Any, Any] = {}


def fresh_live() -> Any:
    live.clear()
    live["a"] = Obj(1)
    live["b"] = 0
    live["z"] = [Obj(2), {"q": Obj(3)}]
    return live


def ins_default(o: Any) -> Any:
    live["c" + str(len(live))] = len(live)
    return o.v


def del_default(o: Any) -> Any:
    if "b" in live:
        del live["b"]
    return o.v


def swap_default(o: Any) -> Any:
    live["z"] = "swapped"
    live[(1, 2)] = "bad"
    return o.v


def cases(tag: str, n: int, kind: int) -> None:
    plain = 0 if kind == 3 else kind  # (sorting needs keys of one type)
    run(tag + " plain", wrap(payload(), n, kind))
    run(tag + " compact", wrap(payload(), n, kind), compact=True, ensure_ascii=False)
    run(tag + " keys", wrap(keyed(), n, kind))
    run(tag + " sorted", wrap({"b": 1, "a": {"d": 1, "c": 2}}, n, plain), sort_keys=True)
    run(tag + " sorted mixed", wrap(keyed(), n, kind), sort_keys=True)
    run(tag + " bad key", wrap({"a": 1, (1, 2): 2, "b": 3}, n, kind))
    run(tag + " skip", wrap({"a": 1, (1, 2): 2, "b": {(3,): 4}}, n, kind), skipkeys=True)
    run(tag + " skip sorted", wrap({"b": 1, (1, 2): 2, "a": {(3,): 4}}, n, plain), skipkeys=True, sort_keys=True)
    run(tag + " nan", wrap([float("nan"), float("inf")], n, kind))
    run(tag + " no nan", wrap([1, float("-inf")], n, kind), allow_nan=False)
    run(tag + " unserializable", wrap([1, Obj(2)], n, kind))
    run(tag + " default", wrap([Obj([Obj({"k": Obj((1, Obj("s")))})]), Chain(5), Chain(3, [1, {"a": Chain(2)}])], n, kind),
        fn=default)
    run(tag + " default raises", wrap([1, {"a": Loop}], n, kind), fn=default)
    run(tag + " default loop", wrap([1, Loop()], n, kind), fn=default)
    run(tag + " inserted", wrap(fresh_live(), n, kind), fn=ins_default)
    run(tag + " deleted", wrap(fresh_live(), n, kind), fn=del_default)
    run(tag + " swapped", wrap(fresh_live(), n, kind), fn=swap_default)
    run(tag + " swapped skip", wrap(fresh_live(), n, kind), fn=swap_default, skipkeys=True)
    run(tag + " inserted sorted", wrap(fresh_live(), n, plain), fn=ins_default, sort_keys=True)
    cyclic: list[Any] = [1]
    top = wrap(cyclic, n, kind)
    cyclic.append(top)
    run(tag + " cycle", top)
    around: dict[str, Any] = {"a": 1}
    top = wrap(around, n, kind)
    around["b"] = [top]
    run(tag + " cycle dict", around)
    through = Obj(None)
    top = wrap([through], n, kind)
    through.v = top
    run(tag + " cycle default", top, fn=default)
    shared: list[Any] = [1, 2]
    run(tag + " shared", wrap([shared, shared, {"a": shared, "b": (shared, shared)}], n, kind))


def indented(tag: str, n: int, kind: int) -> None:
    run(tag + " indent", wrap(payload(), n, kind), indent=1)
    run(tag + " indent keys", wrap(keyed(), n, kind), indent="\t")
    run(tag + " indent skip", wrap({(1, 2): 2, (3,): {(4,): 5}, "e": []}, n, kind), indent=2, skipkeys=True)
    run(tag + " indent default", wrap([Obj([Obj({"k": Obj((1, Obj("s")))})]), Chain(3, [1, {"a": Chain(2)}])], n, kind),
        fn=default, indent=3)


def encoding() -> None:
    for kind in range(4):
        for n in (0, 63, 64, 65, 90):
            cases("k%d n%d" % (kind, n), n, kind)
        for n in (63, 64, 66):
            indented("k%d n%d" % (kind, n), n, kind)
    # The bounds: 9,998 containers and conversions in progress, and one more level for a call
    # of default(), whatever the recursion limit. (spin() reaches them with two objects: a test
    # that also runs with a collection at every allocation cannot afford 9,998 nested
    # containers, which tests/programs/library/json_deep_nesting.py and the json_repair port's
    # tests encode.)
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(160)
    run("4998 lists and conversions", spin(4997, 0), fn=unroll, check_circular=False, compact=True)
    sys.setrecursionlimit(limit)
    run("4999 lists and conversions", spin(4998, 0), fn=unroll, check_circular=False)
    run("18 containers in 4990 and 4990", spin(4989, wrap(1, 18, 3)), fn=unroll, check_circular=False)
    run("19 containers in 4990 and 4990", spin(4989, wrap(1, 19, 3)), fn=unroll, check_circular=False)
    run("looked for", spin(3, 0), fn=unroll)
    # a container that holds itself, found or, unlooked for, followed to the bound
    for n in (0, 70):
        cyclic: list[Any] = [1]
        top = wrap(cyclic, n, 3)
        cyclic.append(top)
        run("cycle in %d" % n, top)
        run("loop in %d" % n, wrap(Loop(), n, 0), fn=default)
    endless: list[Any] = []
    endless.append(endless)
    run("unchecked cycle", endless, check_circular=False)
    run("unchecked loop", Loop(), fn=default, check_circular=False)


decoding()
encoding()
