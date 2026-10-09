# dictfuse's equal values across exception edges (docs/typed-ir.md 7.1): a handler's load of a
# local, a global or a dict reads what was stored before the op that raised, not what the try
# body stores after it. The walk back from a load (Gen.reaching) stops at a landing block, whose
# predecessors the unwind edges leave where an op raised, so `k in d` in a handler and `d["b"]`
# after it are two lookups of different keys, each with its own KeyError.
K = "a"
G: dict[str, int] = {"a": 1, "b": 2, "c": 3, "d": 4}
H: dict[str, int] = {"z": 9}


def g(n: int) -> int:
    if n > 0:
        raise ValueError("boom")
    return n


def straight(d: dict[str, int]) -> None:
    k = "a"
    try:
        int("x")
        k = "b"
    except ValueError:
        if k in d:
            print(d["b"])


def var_key(d: dict[str, int], k2: str, n: int) -> int:
    k = "a"
    try:
        g(n)
        k = k2
    except ValueError:
        if k in d:
            return d[k2]
    return -1


def global_key(d: dict[str, int], n: int) -> None:
    global K
    try:
        g(n)
        K = "b"
    except ValueError:
        if K in d:
            print("found", d["b"])


def after_try(d: dict[str, int], n: int) -> int:
    k = "a"
    try:
        g(n)
        k = "b"
        return 0
    except ValueError:
        pass
    if k in d:
        return d["b"]
    return -1


def dict_alias(d1: dict[int, int], d2: dict[int, int], s: str) -> int:
    d = d1
    try:
        int(s)
        d = d2
    except ValueError:
        if 40 in d:
            return d2[40]
    return -1


def dict_alias_set(d1: dict[str, int], d2: dict[str, int], s: str) -> None:
    d = d1
    try:
        int(s)
        d = d2
    except ValueError:
        if "k40" in d:
            d2["k40"] = 5


def lookup_raises(d: dict[str, int], d2: dict[str, int], k: str, k2: str) -> None:
    try:
        v = d[k]
        k = k2
        print(v)
    except KeyError:
        if k in d2:
            print("d2", d2[k2])


def in_loop(d: dict[str, int], ks: list[str]) -> int:
    t = 0
    for n in range(4):
        k = ks[n]
        try:
            g(n % 2)
            k = "zz"
        except ValueError:
            if k in d:
                t += d["zz"]
            continue
        t += 1
    return t


def template(d, a, b, n):
    k = a
    try:
        g(n)
        k = b
    except ValueError:
        if k in d:
            return d[b]
    return d[a]


def finally_copy(d: dict[str, int], s: str) -> None:
    k = "a"
    try:
        int(s)
        k = "b"
    finally:
        if k in d:
            print("finally", d["b"])


def nested(d: dict[str, int], s: str, t: str) -> str:
    k = "a"
    try:
        try:
            int(s)
            k = "b"
        except ValueError:
            if k in d:
                return str(d["b"])
        int(t)
    except ValueError:
        return "outer"
    return "end"


def global_dict(s: str) -> int:
    global G
    try:
        int(s)
        G = H
    except ValueError:
        if "d" in G:
            return H["d"]
    return 0


def run(name: str, n: int) -> None:
    try:
        if name == "straight":
            straight({"a": 1})
        elif name == "var_key":
            print(var_key({"a": 1}, "zz", n))
        elif name == "global_key":
            global_key({"a": 1}, n)
        elif name == "after_try":
            print(after_try({"a": 1}, n))
        elif name == "dict_alias":
            d1: dict[int, int] = {}
            for i in range(100):
                d1[i] = i
            print(dict_alias(d1, {1: 7}, "x"))
        elif name == "dict_alias_set":
            s1: dict[str, int] = {}
            for i in range(50):
                s1[f"k{i}"] = i
            s2 = {"a": 7}
            dict_alias_set(s1, s2, "x")
            print(s2)
        elif name == "lookup_raises":
            lookup_raises({}, {"x": 3}, "x", "y")
        elif name == "in_loop":
            print(in_loop({"a": 1, "b": 2, "c": 3, "d": 4}, ["a", "b", "c", "d"]))
        elif name == "template":
            print(template({"a": 1}, "a", "b", n), template({1: 10}, 1, 2, n))
        elif name == "finally_copy":
            finally_copy({"a": 1}, "x" if n > 0 else "1")
        elif name == "nested":
            print(nested({"a": 1}, "x" if n > 0 else "1", "1"))
        else:
            print(global_dict("x" if n > 0 else "1"))
    except KeyError as e:
        print(name, n, "KeyError", e)
    except ValueError as e:
        print(name, n, "ValueError", e)


for name in ["straight", "var_key", "global_key", "after_try", "dict_alias", "dict_alias_set", "lookup_raises", "in_loop", "template", "finally_copy", "nested", "global_dict"]:
    for n in [1, 0]:
        run(name, n)
