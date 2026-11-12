# A conditional expression joins a tuple[int, ...] arm and a fixed tuple holding None into a
# tuple[int | None, ...]: the int tuple's items are boxed in its own arm, either order, for each
# outcome of the test
import sys


def ints() -> tuple[int, ...]:
    return tuple([1, 2])


for flag in [len(sys.argv) > 5, len(sys.argv) < 5]:
    t = ints() if flag else (None, 3, 4)
    u = (None, 5) if flag else ints()
    print(t, len(t), t[0] is None, u, len(u), u[-1])
