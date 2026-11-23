# isinstance() with list, tuple, dict, set or frozenset narrows a value of object to a read-only
# view of the container it holds, whatever its items' types: len(), truth, iteration, in, items
# by index (index() and count()) or a dict's values by key (get(), keys(), values(), items()),
# each item a value of object, with CPython's errors; the view is the container itself, which
# its other names change, and a value of object again where one is expected
def show(v: object) -> None:
    x: object = v
    if isinstance(x, list):
        print("list", len(x), x, bool(x))
        for item in x:
            print("  item", item)
        if len(x) > 0:
            print("  first", x[0], "last", x[-1])
        print("  in", 2 in x, "a" in x, 2.0 in x, None in x)
    elif isinstance(x, tuple):
        print("tuple", len(x), x)
        for item in x:
            print("  item", item)
        if len(x) > 1:
            print("  second", x[1], x.index(x[1]), x.count(x[0]), x[-len(x)])
    elif isinstance(x, dict):
        print("dict", len(x), x)
        for k in x:
            print("  key", k, x[k])
        print("  get", x.get("a"), x.get("zz", 0), x.get(1, "none"))
        for k, val in x.items():
            print("  pair", k, val)
        for val in x.values():
            print("  value", val)
        for k in x.keys():
            print("  k", k)
    elif isinstance(x, (set, frozenset)):
        print("set", len(x), 1 in x, "a" in x, 1.0 in x)
        for item in x:
            print("  element", item)
    else:
        print("other", x)


def lookup(m: object, k: object) -> str:
    mapping: object = m
    key: object = k
    if isinstance(mapping, dict):
        try:
            return f"found {mapping[key]}"
        except KeyError as e:
            return f"KeyError {e}"
        except TypeError as e:
            return f"TypeError {e}"
    return "not a dict"


def search(s: object, item: object) -> str:
    seq: object = s
    if isinstance(seq, (list, tuple)):
        try:
            return f"at {seq.index(item)}, {seq.count(item)} times"
        except ValueError as e:
            return f"ValueError {e}"
    return "not a sequence"


def at(s: object, i: int) -> str:
    seq: object = s
    if isinstance(seq, (list, tuple)):
        try:
            return f"{seq[i]}"
        except IndexError as e:
            return f"IndexError {e}"
    return "not a sequence"


def widen(v: object, flag: bool) -> object:
    x: object = v
    if isinstance(x, list):
        y = x
        if flag:
            y = 0
        return y if len(x) > 0 else "empty"
    return None


def main() -> None:
    values: list[object] = [[1, 2, 3], ["a", "b"], (1, "x", 2.5), (), {"a": 1, "b": 2}, {1: "one"}, {1, 2}, frozenset({"a"}), frozenset(), 7]
    for v in values:
        show(v)
    ints = {1: "one", 2: "two"}
    print(lookup(ints, 1), lookup(ints, 1.0), lookup(ints, True), lookup(ints, 3), lookup(ints, "1"))
    print(lookup(ints, [1]), lookup({"a": 1}, "a"), lookup({"a": 1}, "b"), lookup({"a": 1}, 1), lookup(7, 1))
    print(search([1, 2, 2], 2), search([1, 2], 2.0), search((1, "x"), "x"), search([1], 9), search((1,), 9), search(5, 1))
    print(at([1, 2], 1), at([1, 2], -2), at([1, 2], 2), at((1, "x"), -1), at((1, "x"), 2), at((), 0))
    print(widen([1], True), widen([1], False), widen([0][1:], False), widen(3, True))
    nums = [1, 2, 3]
    o: object = nums
    if isinstance(o, list):
        nums.append(4)
        print(o is nums, len(o), o[-1], o)
        for i in o:
            if i == 2:
                nums.append(5)
            print("live", i)
        kept: list[object] = [o]
        print(kept[0] is nums, kept)
    d = {"a": 1}
    od: object = d
    if isinstance(od, dict):
        try:
            for k in od:
                d["b"] = 2
                print("key", k)
        except RuntimeError as e:
            print("RuntimeError", e)
        print(type(od).__name__, f"{od!r}", format(od, ""), not od, od == d)
    s: object = {3}
    if isinstance(s, set):
        try:
            print([1] in s)
        except TypeError as e:
            print("TypeError", e)
    nested: list[object] = [(1, [2, 3]), ("t", 4)]
    for n in nested:
        if isinstance(n, (list, tuple)):
            for inner in n:
                if isinstance(inner, list):
                    print("inner", len(inner), inner[0], inner)


main()
