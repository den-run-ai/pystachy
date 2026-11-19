# listguard where a loop appends to a list, or calls a function that only assigns an item (rng): no
# list gets shorter while it runs, so the tests before it stay true and it runs a copy whose inline
# item reads carry TBAA tags (.tbaa); a loop that calls a function that may shorten a list (popping)
# keeps its checks and gets no copy
def doubled(a: list[float]) -> list[float]:
    out: list[float] = []
    for i in range(len(a)):
        out.append(a[i] * 2.0)
    return out


def bump(state: list[int], i: int) -> int:
    state[i] = state[i] * 5 + 1
    return state[i]


def rng(xs: list[float], state: list[int]) -> float:
    t = 0.0
    for i in range(len(xs)):
        t += xs[i] * bump(state, 0)
    return t


def drop(xs: list[int]) -> int:
    return xs.pop()


def popping(a: list[int], n: int) -> int:
    s = 0
    for i in range(n):
        s += a[i] + drop(a)
    return s


print(doubled([1.0, 2.0]), rng([1.0, 2.0], [1]), bump([3], 0), drop([4]), popping([1, 2, 3, 4], 2))
