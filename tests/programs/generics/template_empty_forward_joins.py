# Forwarded empties keep the ordinary call's layout when recursion or None
# consumes it, while later concrete returns still type fresh allocations.
def empty(n):
    out = []
    return out


def emptyd(n):
    out = {}
    return out


def collect(n):
    if n == 0:
        return emptyd(n)
    r = collect(n - 1)
    r[n] = n
    return r


print(collect(3))


def first(n):
    if n == 0:
        return empty(n)
    r = second(n - 1)
    r.append(n)
    return r


def second(n):
    if n == 0:
        return empty(n)
    r = first(n - 1)
    r.append(n)
    return r


print(first(4), second(3))


def optional_dict(c, n):
    if c:
        return None
    return emptyd(n)


def optional_list(c, n):
    if c:
        return empty(n)
    return None


def optional_bare(c, n):
    if c:
        return emptyd(n)
    return


print(optional_dict(True, 0), optional_dict(False, 0))
print(optional_list(True, 0), optional_list(False, 0))
print(optional_bare(True, 0), optional_bare(False, 0))


def double(xs):
    if not xs:
        return empty(0)
    return [x * 2 for x in xs]


empty_ints: list[int] = []
print(double([1, 2]), double(empty_ints), double([1.5]), double(["a"]))


# The earlier returned empty allocation gets the joined dict's actual key kind.
def tuple_keys(c, n):
    if c:
        return emptyd(n)
    return {("key", n): n}


pairs = tuple_keys(True, 4)
pairs["insert", 5] = 6
print(pairs["insert", 5], tuple_keys(False, 4))


# An explicit optional context still chooses its native string/tuple key layout.
a: dict[str, int] | None = optional_dict(False, 0)
b: dict[tuple[str, int], int] | None = optional_bare(True, 0)
c: list[str] | None = optional_list(True, 0)
if a is not None:
    a["name"] = 7
    print(a["name"])
if b is not None:
    b["name", 8] = 9
    print(b["name", 8])
if c is not None:
    c.append("value")
    print(c)


# A matching annotated recursive layout is safe too, including non-int keys.
def recursive_strings(n):
    if n == 0:
        return emptyd(n)
    r: dict[str, int] = recursive_strings(n - 1)
    r[str(n)] = n
    return r


print(recursive_strings(2))


def no_result(n):
    pass


def optional_call(c, n):
    if c:
        return empty(n)
    return no_result(n)


print(optional_call(True, 0), optional_call(False, 0))
