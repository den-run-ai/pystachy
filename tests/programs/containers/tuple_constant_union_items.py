# The items of a constant tuple (#1016) that a loop reads from its slots, passed as a union's
# members: each union box takes its item with the item's type, which the IR check proves from
# the constant's own type (tupleiter reads the slots through a machine address).
def show(x: int | str | None) -> str:
    return repr(x)


def run() -> list[str]:
    out: list[str] = []
    for seed in 1, 12, 123:
        out.append(show(seed))
    for name in ("a", "bc"):
        out.append(show(name))
    for k in (None, None):
        out.append(show(k))
    return out


print(run())
