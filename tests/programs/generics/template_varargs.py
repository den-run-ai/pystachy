# *args: one function per call arity, the extra arguments a tuple of their types
def total(*nums):
    s = 0
    for n in nums:
        s += n
    return s


def join(sep, *parts):
    out = ""
    for p in parts:
        if out:
            out += sep
        out += p
    return out


def describe(first, *rest, upper=False):
    r = f"{first}: {len(rest)} more"
    if rest:
        r += f", last {rest[-1]}"
    return r.upper() if upper else r


def count(*args: int) -> int:
    return len(args)


def show(*xs):
    return repr(xs)


print(total(), total(1), total(1, 2, 3), total(4, 5))
print(join("-"), join("-", "a"), join(", ", "x", "y", "z"))
print(describe("a"), describe("b", 1, 2), describe("c", "x", upper=True))
print(count(), count(1, 2), show(), show(1), show(1, "a"), () == (), len(()), bool(()), not ())
empty = ()
print(empty, repr(empty), empty == (), 3 in ())
