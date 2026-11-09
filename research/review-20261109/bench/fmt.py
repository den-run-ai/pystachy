import time
from typing import Callable


def f_int(n: int) -> int:
    t = 0
    for i in range(n):
        t += len(f"{i}")
    return t


def f_str_int(n: int) -> int:
    t = 0
    for i in range(n):
        t += len(str(i))
    return t


def f_int_width(n: int) -> int:
    t = 0
    for i in range(n):
        t += len(f"{i:>8}")
    return t


def f_int_pad0(n: int) -> int:
    t = 0
    for i in range(n):
        t += len(f"{i:08d}")
    return t


def f_int_hex(n: int) -> int:
    t = 0
    for i in range(n):
        t += len(f"{i:x}")
    return t


def f_float_3f(n: int) -> int:
    t = 0
    for i in range(n):
        t += len(f"{i / 7:.3f}")
    return t


def f_float_repr(n: int) -> int:
    t = 0
    for i in range(n):
        t += len(f"{i / 7}")
    return t


def f_float_g(n: int) -> int:
    t = 0
    for i in range(n):
        t += len(f"{i / 7:g}")
    return t


def f_float_e(n: int) -> int:
    t = 0
    for i in range(n):
        t += len(f"{i / 7:.2e}")
    return t


def f_str_pad(n: int) -> int:
    t = 0
    s = "abc"
    for i in range(n):
        t += len(f"{s:>10}")
    return t


def f_concat3(n: int) -> int:
    t = 0
    s = "abc"
    for i in range(n):
        t += len(f"{s}-{s}-{s}")
    return t


def f_pct(n: int) -> int:
    t = 0
    for i in range(n):
        t += len("%d:%8d|%.3f" % (i, i * 2, i / 7))
    return t


def f_format(n: int) -> int:
    t = 0
    for i in range(n):
        t += len("{}:{:>8}|{:.3f}".format(i, i * 2, i / 7))
    return t


def f_int_parse(n: int) -> int:
    t = 0
    ss = [str(i * 37) for i in range(1000)]
    for i in range(n):
        t += int(ss[i % 1000])
    return t


def f_float_parse(n: int) -> float:
    t = 0.0
    ss = [str(i / 7) for i in range(1000)]
    for i in range(n):
        t += float(ss[i % 1000])
    return t


def f_repr_str(n: int) -> int:
    t = 0
    s = "hello 'world'\n"
    for i in range(n):
        t += len(repr(s))
    return t


def f_list_str(n: int) -> int:
    t = 0
    xs = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    for i in range(n // 10):
        t += len(str(xs))
    return t


def f_round(n: int) -> float:
    t = 0.0
    for i in range(n):
        t += round(i / 7, 2)
    return t


BENCHES: list[tuple[str, Callable[[int], str]]] = [
    ("f_int", lambda n: str(f_int(n))), ("str_int", lambda n: str(f_str_int(n))), ("f_int_width", lambda n: str(f_int_width(n))),
    ("f_int_pad0", lambda n: str(f_int_pad0(n))), ("f_int_hex", lambda n: str(f_int_hex(n))), ("f_float_3f", lambda n: str(f_float_3f(n))),
    ("f_float_repr", lambda n: str(f_float_repr(n))), ("f_float_g", lambda n: str(f_float_g(n))), ("f_float_e", lambda n: str(f_float_e(n))),
    ("f_str_pad", lambda n: str(f_str_pad(n))), ("f_concat3", lambda n: str(f_concat3(n))), ("pct", lambda n: str(f_pct(n))), ("format", lambda n: str(f_format(n))),
    ("int_parse", lambda n: str(f_int_parse(n))), ("float_parse", lambda n: str(f_float_parse(n))), ("repr_str", lambda n: str(f_repr_str(n))),
    ("list_str", lambda n: str(f_list_str(n))), ("round2", lambda n: str(f_round(n))),
]


def main() -> None:
    for name, fn in BENCHES:
        t0 = time.perf_counter()
        r = fn(2000000)
        print(f"{name}\t{time.perf_counter() - t0:.4f}\t{r}")


main()
