# json.loads() nests as deep as CPython's C decoder does, 9,998 containers, whatever the recursion
# limit: the containers past the first 64 are decoded without a call for each. What it returns, the
# error past the bound and the positions of errors in deep text are CPython's.
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


def main() -> None:
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


main()
