# A conditional expression as the left operand of a binary operator, where the operation's
# result is wanted as a closed union: the union is the result's, so arms of one type keep it
# and the operation runs on that type (it was rejected: "closed union arithmetic requires
# narrowing", or ran as union arithmetic for int | float). Arms of two types, which make the
# union: scalar_union_conditional_mixed.py
import sys


def ret_mul(a: int, c: int) -> int | str:
    return (a if a > 0 else c) * 2


def ret_chain(a: int, c: int) -> int | str:
    return ((a if a > 0 else c) + 1) * 3 - (c if c else a) % 5


def ret_str(a: str, c: str) -> int | str:
    return (a if a else c) + "x"


def ret_float(a: float, c: float) -> float | str:
    return (a if a > 0 else c) / 2


def ret_opt_union(a: int, c: int) -> int | str | None:
    return (a if a > 0 else c) + 1


def ret_numeric(a: int, c: int) -> int | float:
    return (a if a > 0 else c) * 2


def ret_pow(a: int, c: int) -> int | float:
    return (a if a > 0 else c) ** 2


def ret_bits(a: int, c: int) -> int | float:
    return ((a if a > 0 else c) & 7) + ((a if a > 0 else c) << 2) + ((c if a > 0 else a) >> 1) + ((a if a > 0 else c) | 8) + ((a if a > 0 else c) ^ 1)


def ret_mixed_str(a: int, flag: bool) -> list[int | str]:
    out: list[int | str] = []
    v: int | str = a if flag else "s"
    out.append(v)
    out.append((a if flag else a + 1) - 1)
    return out


def ret_nested(a: int, c: int) -> int | str:
    return (a if a > 5 else (c if c > 5 else a + c)) * 10


def ret_static(a: int, c: int) -> int | str:
    return (a if True else c) + (c if False else a) * 2


def ret_order(log: list[str], a: int) -> int | str:
    def t(name: str, v: int) -> int:
        log.append(name)
        return v

    return (t("then", a) if t("cond", a) > 0 else t("else", -a)) * t("right", 2)


def ret_div0(a: int, c: int) -> int | str:
    return (a if a > 0 else c) // (a - a)


def show(v: int | str) -> str:
    return repr(v)


class Cfg:
    def __init__(self, n: int) -> None:
        self.v: int | str = (n if n > 0 else -n) * 2
        self.w: float | str = (0.5 if n > 0 else 1.5) + n


def items(n: int) -> list[int | str]:
    return [(n if n > 0 else -n) + 1, "a", ("x" if n else "y") * 2]


def pair(n: int) -> tuple[int | str, int]:
    return ((n if n > 0 else -n) + 1, 2)


def main(z: int) -> None:
    print(ret_mul(3, 4), ret_mul(-3, 4), ret_chain(3, 4), ret_chain(-3, 0), ret_str("", "q"), ret_str("p", "q"))
    print(ret_float(3.0, 4.0), ret_float(-3.0, 5.0), ret_opt_union(3, 4), ret_opt_union(-1, 9))
    print(ret_numeric(3, 4), ret_numeric(-3, 4), ret_pow(3, 4), ret_pow(-3, 4), ret_bits(3, 4), ret_bits(-3, 4))
    print(ret_mixed_str(3, True), ret_mixed_str(3, False))
    print(ret_nested(9, 1), ret_nested(1, 9), ret_nested(1, 2), ret_static(3, 4))
    log: list[str] = []
    print(ret_order(log, 3), ret_order(log, -3), log)
    try:
        print(ret_div0(3 + z, 4))
    except ZeroDivisionError as e:
        print("ZeroDivisionError", e)
    a = 3 + z
    c = 4
    print(show((a if a > 0 else c) * 2), show(("s" if a > 0 else "t") + "!"))
    vals: dict[str, int | str] = {}
    vals["n"] = (a if a > 2 else 0) + 1
    vals["s"] = ("x" if a > 2 else "y") + "!"
    u: int | str = 0
    u = (a if a > 0 else c) * 2
    print(vals, u, Cfg(-3).v, Cfg(3).w, Cfg(-3).w, items(-3), items(0), pair(-3))
    r = ret_mul(1, 2)
    print(isinstance(r, int), type(ret_numeric(1, 2)).__name__, type(ret_str("a", "b")).__name__)


main(len(sys.argv) - 1)
