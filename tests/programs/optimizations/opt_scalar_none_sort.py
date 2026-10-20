# An int, float or bool | None that is None, used where only a value works, raises CPython's
# error (sorted, max of a list)


def use(xs: list[int | None]) -> None:
    print("using", xs, sorted(xs[1:]), max(xs[1:]), min(xs[1:]))
    print(max(xs))


use([None, 3, 1])
