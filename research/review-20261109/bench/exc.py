import time
from typing import Callable


class MyErr(Exception):
    pass


def e_local_raise(n: int) -> int:
    t = 0
    for i in range(n):
        try:
            raise ValueError("x")
        except ValueError:
            t += 1
    return t


def thrower(i: int) -> int:
    if i >= 0:
        raise ValueError("x")
    return i


def e_callee_raise(n: int) -> int:
    t = 0
    for i in range(n):
        try:
            t += thrower(i)
        except ValueError:
            t += 1
    return t


def thrower_user(i: int) -> int:
    if i >= 0:
        raise MyErr("x")
    return i


def e_callee_user(n: int) -> int:
    t = 0
    for i in range(n):
        try:
            t += thrower_user(i)
        except MyErr:
            t += 1
    return t


def deep(i: int, d: int) -> int:
    if d == 0:
        raise ValueError("deep")
    return deep(i, d - 1) + 1


def e_deep10(n: int) -> int:
    t = 0
    for i in range(n):
        try:
            t += deep(i, 10)
        except ValueError:
            t += 1
    return t


def e_keyerror(n: int) -> int:
    d: dict[int, int] = {1: 1}
    t = 0
    for i in range(n):
        try:
            t += d[i + 2]
        except KeyError:
            t += 1
    return t


def e_keyerror_str(n: int) -> int:
    d: dict[str, int] = {"a": 1}
    t = 0
    for i in range(n):
        try:
            t += d["missing"]
        except KeyError:
            t += 1
    return t


def e_indexerror(n: int) -> int:
    xs = [1, 2, 3]
    t = 0
    for i in range(n):
        try:
            t += xs[i + 3]
        except IndexError:
            t += 1
    return t


def e_int_parse(n: int) -> int:
    t = 0
    for i in range(n):
        try:
            t += int("x12")
        except ValueError:
            t += 1
    return t


def e_stopiter(n: int) -> int:
    t = 0
    xs: list[int] = []
    for i in range(n):
        it = iter(xs)
        try:
            t += next(it)
        except StopIteration:
            t += 1
    return t


def e_attr_none(n: int) -> int:
    t = 0
    s: str | None = None
    for i in range(n):
        try:
            t += len(s.upper())
        except AttributeError:
            t += 1
    return t


def e_zero_div(n: int) -> int:
    t = 0
    z = 0
    for i in range(n):
        try:
            t += i // z
        except ZeroDivisionError:
            t += 1
    return t


def e_try_no_raise(n: int) -> int:
    t = 0
    d: dict[int, int] = {1: 1}
    for i in range(n):
        try:
            t += d[1]
        except KeyError:
            t += 100
    return t


def e_finally(n: int) -> int:
    t = 0
    for i in range(n):
        try:
            t += 1
        finally:
            t += 1
    return t


def e_dict_get(n: int) -> int:
    d: dict[int, int] = {1: 1}
    t = 0
    for i in range(n):
        v = d.get(i + 2)
        if v is None:
            t += 1
        else:
            t += v
    return t


BENCHES: list[tuple[str, Callable[[int], int]]] = [
    ("local_raise", e_local_raise), ("callee_raise", e_callee_raise), ("callee_user_exc", e_callee_user), ("deep10", e_deep10),
    ("keyerror_int", e_keyerror), ("keyerror_str", e_keyerror_str), ("indexerror", e_indexerror), ("int_parse_err", e_int_parse),
    ("stopiteration", e_stopiter), ("attr_none", e_attr_none), ("zero_div", e_zero_div), ("try_no_raise", e_try_no_raise), ("finally", e_finally), ("dict_get_miss", e_dict_get),
]


def main() -> None:
    n = 500000
    for name, fn in BENCHES:
        t0 = time.perf_counter()
        r = fn(n)
        dt = time.perf_counter() - t0
        print(f"{name}\t{dt:.4f}\t{r}")


main()
