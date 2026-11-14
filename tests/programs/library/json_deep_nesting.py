# json.loads() and json.dumps() nest as deep as CPython's C decoder and encoder do, 9,998
# containers, whatever the recursion limit: the containers past the first 64 are decoded and encoded
# without a call for each. What they return, the errors past the bound, the positions of errors in
# deep text and the circular references found in deep values are CPython's.
import json
import sys


def depth_of(value: "json.JSONValue") -> int:
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
        value: json.JSONValue = json.loads(source)
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
    value: json.JSONValue = json.loads(wide)
    for _ in range(79):
        if isinstance(value, list):
            value = value[0]
    print(json.dumps(value))
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(160)
    print("low limit", probe("[" * 2001 + "0" + "]" * 2001))
    sys.setrecursionlimit(limit)


def nest(depth: int, dicts: bool) -> "json.JSONValue":
    value: json.JSONValue = [1, "x", None, True, 2.5, {"k": [], "j": {}}]
    for i in range(depth - 1):
        if dicts and i % 2 == 0:
            inner: dict[str, json.JSONValue] = {"b": i, "a": value, "c": [i]}
            value = inner
        else:
            outer: list[json.JSONValue] = [i, value, "s"]
            value = outer
    return value


def chain(depth: int) -> "json.JSONValue":
    value: json.JSONValue = [0]
    for _ in range(depth - 1):
        outer: list[json.JSONValue] = [value]
        value = outer
    return value


def show(text: str) -> None:
    print(len(text), text[:36], text[-36:])


def attempt(value: "json.JSONValue") -> None:
    try:
        show(json.dumps(value))
    except RecursionError as exc:
        print("RecursionError", exc)
    except ValueError as exc:
        print("ValueError", exc)


def encoding() -> None:
    for n in (1, 63, 64, 65, 66, 67, 130):
        for dicts in (False, True):
            value = nest(n, dicts)
            text = json.dumps(value)
            show(text)
            show(json.dumps(value, sort_keys=True, separators=(",", ":")))
            show(json.dumps(value, indent=1))
            show(json.dumps(value, indent="\t", sort_keys=True))
            print(json.dumps(json.loads(text)) == text)
    # (the bound, on one value: a test that also runs with a collection at every allocation
    # cannot afford more of these)
    deep = chain(9998)
    attempt(deep)
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(160)
    attempt(deep)
    sys.setrecursionlimit(limit)
    beyond: list[json.JSONValue] = [deep]
    attempt(beyond)
    # a container that holds itself past the 64th
    cyclic: list[json.JSONValue] = [1]
    top: json.JSONValue = cyclic
    for _ in range(100):
        around: list[json.JSONValue] = [top]
        top = around
    cyclic.append(top)
    attempt(top)
    # one that an encoded value past the 64th holds, itself among the first 64
    early: dict[str, json.JSONValue] = {"a": 1}
    inside: list[json.JSONValue] = [early]
    top = inside
    for _ in range(70):
        over: list[json.JSONValue] = [top]
        top = over
    early["b"] = top
    attempt(early)
    # the same container twice is no cycle
    shared: list[json.JSONValue] = [1, 2]
    top = [shared, shared, {"a": shared, "b": shared}]
    for _ in range(70):
        twice: list[json.JSONValue] = [top, shared]
        top = twice
    attempt(top)
    # a value out of range, and one written as CPython writes it, past the 64th container
    odd: json.JSONValue = [float("inf"), -0.0, 1e22, "é ", {"n": float("nan")}]
    for _ in range(70):
        wrapped: list[json.JSONValue] = [odd]
        odd = wrapped
    attempt(odd)
    try:
        json.dumps(odd, allow_nan=False)
    except ValueError as exc:
        print("ValueError", exc)
    print(json.dumps(odd, ensure_ascii=False)[60:140])


decoding()
encoding()
