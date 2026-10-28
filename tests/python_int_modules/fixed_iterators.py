# A module that does not opt in: the iterators of iter() give it the ints that a list, a dict or a
# set holds as the container holds them, as they give a module that opts in.
def first(c):
    return next(iter(c))


def drain(c) -> list[int]:
    out: list[int] = []
    it = iter(c)
    while True:
        x = next(it, None)
        if x is None:
            break
        out.append(x)
    return out


def pairs_of(d: dict[int, int]) -> list[tuple[int, int]]:
    return list(iter(d.items()))


def count(c) -> int:
    n = 0
    for _ in iter(c):
        n += 1
    return n


def keys_of(d: dict[tuple[int, int], str]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for k in iter(d):
        out.append(k)
    return out


def made() -> list[int]:
    return [-9223372036854775807 - 1, 5]


def mixed(c) -> None:
    # (displays of an iterator's int and a float, a bool or a str, as of a 64-bit int and those)
    print(sum([next(iter(c)), 2.0]), [next(iter(c)), True], [next(iter(c)), "a"], {1: next(iter(c)), 2: 2.0})
