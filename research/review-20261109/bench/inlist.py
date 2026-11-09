import sys
import time


def b_in_list(xs: list[int], n: int) -> int:
    t = 0
    for i in range(n):
        if i % 150 in xs:
            t += 1
    return t


def b_in_list_manual(xs: list[int], n: int) -> int:
    t = 0
    for i in range(n):
        k = i % 150
        for x in xs:
            if x == k:
                t += 1
                break
    return t


def b_in_str_list(xs: list[str], n: int) -> int:
    t = 0
    for i in range(n):
        if xs[i % 150 % len(xs)] in xs:
            t += 1
    return t


def b_index(xs: list[int], n: int) -> int:
    t = 0
    for i in range(n):
        t += xs.index(i % 100)
    return t


def b_count(xs: list[int], n: int) -> int:
    t = 0
    for i in range(n):
        t += xs.count(i % 100)
    return t


def b_in_floats(xs: list[float], n: int) -> int:
    t = 0
    for i in range(n):
        if float(i % 150) in xs:
            t += 1
    return t


def b_in_tuple(n: int) -> int:
    t = 0
    for i in range(n):
        if i % 20 in (1, 3, 5, 7, 11, 13, 17, 19):
            t += 1
    return t


def b_in_set(xs: set[int], n: int) -> int:
    t = 0
    for i in range(n):
        if i % 150 in xs:
            t += 1
    return t


def main() -> None:
    n = 1000000
    xs = list(range(100))
    ss = [str(i) for i in range(100)]
    fs = [float(i) for i in range(100)]
    st = set(xs)
    t0 = time.perf_counter(); r = b_in_list(xs, n); print(f"in_list\t{time.perf_counter() - t0:.4f}\t{r}")
    t0 = time.perf_counter(); r = b_in_list_manual(xs, n); print(f"in_list_manual\t{time.perf_counter() - t0:.4f}\t{r}")
    t0 = time.perf_counter(); r = b_in_str_list(ss, n); print(f"in_str_list\t{time.perf_counter() - t0:.4f}\t{r}")
    t0 = time.perf_counter(); r = b_index(xs, n); print(f"index\t{time.perf_counter() - t0:.4f}\t{r}")
    t0 = time.perf_counter(); r = b_count(xs, n); print(f"count\t{time.perf_counter() - t0:.4f}\t{r}")
    t0 = time.perf_counter(); r = b_in_floats(fs, n); print(f"in_floats\t{time.perf_counter() - t0:.4f}\t{r}")
    t0 = time.perf_counter(); r = b_in_tuple(n * 10); print(f"in_tuple\t{time.perf_counter() - t0:.4f}\t{r}")
    t0 = time.perf_counter(); r = b_in_set(st, n * 10); print(f"in_set\t{time.perf_counter() - t0:.4f}\t{r}")


main()
