# Range loops whose item reads and assignments run unchecked though the loop appends, inserts or
# extends (listguard: no list gets shorter while it runs, so lengths read before it stay lower
# bounds), and loops that shorten a list or call a function that writes one, which keep their
# checks: every result, and every IndexError with the iterations before it, is CPython's
def doubled(a: list[float]) -> list[float]:
    out: list[float] = []
    for i in range(len(a)):
        out.append(a[i] * 2.0)
    return out


def products(a: list[float], b: list[float], n: int) -> list[float]:
    return [a[i] * b[i] for i in range(n)]


def self_append(a: list[int]) -> list[int]:
    for i in range(len(a)):
        a.append(a[i] + 1)
    return a


def front(a: list[int], n: int) -> list[int]:
    out = [0]
    for i in range(n):
        out.insert(0, a[i])
        out.extend([a[i] * 10])
        a[i] = len(out)
    return out


def bump(state: list[int], i: int) -> int:
    state[i] = (state[i] * 5 + 1) % 65536
    return state[i]


def rng(xs: list[float], state: list[int]) -> float:
    t = 0.0
    for i in range(len(xs)):
        t += xs[i] * bump(state, i % 3)
    return t


def deeper(state: list[int], i: int) -> int:
    return bump(state, i) + bump(state, i + 1)


def rng2(xs: list[float], state: list[int], n: int) -> float:
    t = 0.0
    for i in range(n):
        t += xs[i] * deeper(state, i % 2)
        print("rng2", i)
    return t


def drop(xs: list[int]) -> int:
    return xs.pop()


def popping(a: list[int], n: int) -> int:
    s = 0
    for i in range(n):
        s += a[i]
        drop(a)
    return s


def via(a: list[int]) -> int:
    return drop(a)


def popping2(a: list[int], n: int) -> int:
    s = 0
    for i in range(n):
        s += a[i] + via(a) * 0
    return s


def clearing(a: list[int], n: int) -> int:
    s = 0
    for i in range(n):
        s += a[i]
        if i == 1:
            a.clear()
    return s


def deleting(a: list[int], n: int) -> int:
    s = 0
    for i in range(n):
        s += a[i]
        del a[0]
    return s


def sliced(a: list[int], n: int) -> int:
    s = 0
    for i in range(n):
        s += a[i]
        a[0:2] = [9]
    return s


def scaled(a: list[int], n: int) -> int:
    s = 0
    for i in range(n):
        s += a[i]
        a *= 1 if i < 1 else 0
    return s


def recur(a: list[int], k: int) -> int:
    if k == 0:
        a.pop()
        return 0
    return recur(a, k - 1)


def recursive(a: list[int], n: int) -> int:
    s = 0
    for i in range(n):
        s += a[i] + recur(a, i % 2)
    return s


def main() -> None:
    print("doubled", doubled([1.0, 2.5, 4.0]), doubled([]))
    print("products", products([1.0, 2.0, 3.0], [4.0, 5.0, 6.0], 3), products([], [], 0))
    try:
        products([1.0, 2.0, 3.0], [4.0], 2)
    except IndexError as e:
        print("products short", e)
    print("self append", self_append([1, 2, 3]))
    xs = [4, 5, 6]
    print("front", front(xs, 3), xs)
    try:
        front([1], 2)
    except IndexError as e:
        print("front long", e)
    st = [1, 2, 3]
    print("rng", rng([0.5, 1.5, 2.5, 3.5], st), st)
    st2 = [7, 8, 9]
    print("rng2", rng2([1.0, 2.0, 3.0], st2, 3), st2)
    try:
        rng2([1.0], [1, 2, 3], 2)
    except IndexError as e:
        print("rng2 long", e)
    try:
        print("popping", popping([1, 2, 3, 4, 5, 6], 4))
    except IndexError as e:
        print("popping short", e)
    try:
        print("popping", popping([1, 2, 3, 4, 5, 6], 3))
    except IndexError as e:
        print("popping short", e)
    try:
        print("popping2", popping2([1, 2, 3, 4, 5, 6], 4))
    except IndexError as e:
        print("popping2 short", e)
    try:
        print("popping2", popping2([1, 2, 3, 4, 5, 6], 3))
    except IndexError as e:
        print("popping2 short", e)
    try:
        print("clearing", clearing([1, 2, 3, 4, 5, 6], 4))
    except IndexError as e:
        print("clearing short", e)
    try:
        print("clearing", clearing([1, 2, 3, 4, 5, 6], 3))
    except IndexError as e:
        print("clearing short", e)
    try:
        print("deleting", deleting([1, 2, 3, 4, 5, 6], 4))
    except IndexError as e:
        print("deleting short", e)
    try:
        print("deleting", deleting([1, 2, 3, 4, 5, 6], 3))
    except IndexError as e:
        print("deleting short", e)
    try:
        print("sliced", sliced([1, 2, 3, 4, 5, 6], 4))
    except IndexError as e:
        print("sliced short", e)
    try:
        print("sliced", sliced([1, 2, 3, 4, 5, 6], 3))
    except IndexError as e:
        print("sliced short", e)
    try:
        print("scaled", scaled([1, 2, 3, 4, 5, 6], 4))
    except IndexError as e:
        print("scaled short", e)
    try:
        print("scaled", scaled([1, 2, 3, 4, 5, 6], 3))
    except IndexError as e:
        print("scaled short", e)
    try:
        print("recursive", recursive([1, 2, 3, 4, 5, 6], 4))
    except IndexError as e:
        print("recursive short", e)
    try:
        print("recursive", recursive([1, 2, 3, 4, 5, 6], 3))
    except IndexError as e:
        print("recursive short", e)


main()
