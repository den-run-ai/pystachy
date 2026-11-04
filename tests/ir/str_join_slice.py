def joined(xs: list[str], start: int, stop: int) -> str:
    return ".".join(xs[start:stop])


def stepped(xs: list[str], step: int) -> str:
    return ".".join(xs[::step])


def saved(xs: list[str]) -> str:
    tail = xs[1:]
    xs.clear()
    return ".".join(tail)


xs = ["a", "b", "c"]
print(joined(xs, 1, 3), stepped(xs, -1), saved(xs))
