# listget and dictfuse (docs/typed-ir.md 7.1) across exception edges. The passes run before
# eh_ir, where every block a try statement covers goes to its landing block (Gen.preds): a
# landing block starts knowing no lookup, as what holds at the end of a covered block is not
# what holds where one of its ops raised (a getitem that raised KeyError ends its block knowing
# its key is in the dict), so a handler's code fuses only its own lookups, and so does the
# code after the try statement, where the handler's end joins. Inside a try body, and in a
# clause, the passes rewrite as anywhere: a fused op that may raise (pys_dict_entry) becomes an
# invoke to the landing block as any other call. passes_exc.calls pins it (invokes included).


def in_body(d: dict[str, int], k: str) -> None:
    try:
        if k in d:
            d[k] += 1  # find, val, entry_set: fused inside the try body
    except KeyError:
        print("no")


def missing(d: dict[str, int], k: str) -> int:
    try:
        v = d[k]  # a getitem that may raise KeyError
    except KeyError:
        d[k] = 0  # a set: the getitem found no entry
        v = 0
    d[k] = v + 1  # a set: the clause's end joins here
    return v


def resumed(d: dict[str, int], k: str, s: str) -> None:
    if k in d:
        try:
            n = int(s)
        except ValueError:
            del d[k]
            n = 0
        d[k] += n  # getitem and set: the clause that deleted k joins here


def in_clause(d: dict[str, int], k: str, s: str) -> int:
    try:
        return int(s)
    except ValueError:
        if k in d:
            return d[k]  # find, val: the clause's own lookup
        return -1


def total(xs: list[int]) -> int:
    t = 0
    for x in xs:  # the loop's read stays unchecked (no pys_list_get)
        try:
            t += 100 // x
        except ZeroDivisionError:
            xs.pop()
    return t


def total_in_clause(xs: list[int], s: str) -> int:
    try:
        return int(s)
    except ValueError:
        t = 0
        for x in xs:  # (a loop in a clause too)
            t += x
        return t


in_body({"a": 1}, "a")
print(missing({}, "a"), resumed({"a": 1}, "a", "x"), in_clause({"a": 2}, "a", "x"), total([1, 0, 2]), total_in_clause([1, 2], "x"))
