# Dead code after return, raise and sys.exit() whose first instruction is a checked
# arithmetic op: the op's number is taken before the block for the dead code opens.
import sys


def after_return(x: int) -> int:
    return x
    y = 3 * 4
    return y


def after_raise(x: int) -> int:
    if x < 0:
        raise ValueError("negative")
        z = 6 * 7
        print(z)
    return x + 1


def after_exit(x: int) -> int:
    if x > 100:
        sys.exit(3)
        w = 9 - 2
        print(w)
    return x


def loop_return(xs: list[int]) -> int:
    for v in xs:
        if v > 2:
            return v
            t = 2 + 2
            print(t)
    return 0


print(after_return(5), after_raise(2), after_exit(7), loop_return([1, 2, 3]))
