# dictfuse across exception edges (docs/typed-ir.md 7.1): an entry that a lookup found is not
# reused where a handler of the same function may have run since (a handler starts knowing
# nothing, and so does the code after its try statement, where its end joins), and a getitem
# that raised KeyError leaves its key not known to be in the dict.


def handler_deletes(d: dict[str, int], k: str, s: str) -> None:
    if k in d:
        try:
            n = int(s)
        except ValueError:
            del d[k]
            n = 0
        try:
            d[k] += n
        except KeyError as e:
            print("KeyError", e)
    print(sorted(d.items()))


def handler_moves(d: dict[str, int], k: str, s: str) -> None:
    # (the handler moves k's entry: one reused from the has would be another key's)
    if k in d:
        try:
            n = int(s)
        except ValueError:
            v = d.pop(k)
            d["zz"] = 100
            d[k] = v
            n = 1
        d[k] += n
    print(sorted(d.items()))


def missing_then_set(d: dict[str, int], keys: list[str]) -> None:
    for k in keys:
        try:
            v = d[k]
        except KeyError:
            d[k] = 0  # (inserts: the getitem that raised found no entry)
            v = -1
        d[k] = v + 1
    print(sorted(d.items()))


def between(d: dict[str, int], k: str, xs: list[int]) -> int:
    # a call that may raise between the has and the getitem, caught in the same function
    total = 0
    try:
        if k in d:
            total = xs[d[k]]
            d[k] += 1
    except IndexError:
        d.clear()
        d["a"] = 1
        d[k] = 7
    try:
        d[k] += 1
    except KeyError as e:
        print("KeyError", e)
    return total


def has_raise_get(d: dict[str, int], k: str, s: str) -> None:
    try:
        if k in d:
            n = int(s)
            d[k] = d[k] + n
    except ValueError:
        d[k] = -1
        d[k] += 10
    print(sorted(d.items()))


def loop_retry(d: dict[str, int], keys: list[str]) -> None:
    for k in keys:
        try:
            if k in d:
                d[k] += int(k)
            else:
                d[k] = 1
        except ValueError:
            del d[k]
            d["x" + k] = len(d)
    print(sorted(d.items()))


def finally_clears(d: dict[str, int], k: str, s: str) -> None:
    try:
        if k in d:
            try:
                n = int(s)
            finally:
                if s == "bad":
                    d.clear()
            d[k] += n
    except ValueError:
        print("ValueError")
    try:
        print(d[k])
    except KeyError as e:
        print("KeyError", e)


handler_deletes({"a": 1, "b": 2}, "a", "x")
handler_deletes({"a": 1, "b": 2}, "a", "5")
handler_moves({"a": 1, "b": 2, "c": 3}, "a", "x")
handler_moves({"a": 1, "b": 2, "c": 3}, "b", "4")
missing_then_set({"a": 5}, ["a", "b", "b", "c", "a"])
print(between({"k": 1}, "k", [10, 20]), between({"k": 5}, "k", [10, 20]), between({"j": 0}, "k", [3]))
has_raise_get({"a": 1}, "a", "x")
has_raise_get({"a": 1}, "a", "2")
has_raise_get({"b": 1}, "a", "x")
loop_retry({"1": 1, "y": 2, "3": 3}, ["1", "y", "3", "y", "z", "1"])
finally_clears({"a": 1}, "a", "bad")
finally_clears({"a": 1}, "a", "2")
