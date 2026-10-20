# discard() and remove() of a value that may be None, decided at run time: None is no element of
# a set of ints or strs, so discard() does nothing and remove() raises KeyError: None.


def key(n: int) -> int | None:
    return None if n < 0 else n


def name(n: int) -> str | None:
    return None if n < 0 else "k" + str(n)


s = {1, 2, 3}
t = {"k1", "k2"}
for n in [2, -1, 7]:
    s.discard(key(n))
    t.discard(name(n))
    print(n, sorted(s), sorted(t))
for n in [1, -1, 9]:
    try:
        s.remove(key(n))
        print("removed", n, sorted(s))
    except KeyError as e:
        print("KeyError:", e)
    try:
        t.remove(name(n))
        print("removed", n, sorted(t))
    except KeyError as e:
        print("KeyError:", e)
