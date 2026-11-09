import time


def make_words(n: int) -> list[str]:
    return ["w" + str(i % 5000) for i in range(n)]


def count_words(words: list[str]) -> int:
    d: dict[str, int] = {}
    for w in words:
        d[w] = d.get(w, 0) + 1
    return len(d) + d["w42"]


def count_words2(words: list[str]) -> int:
    d: dict[str, int] = {}
    for w in words:
        if w in d:
            d[w] += 1
        else:
            d[w] = 1
    return len(d) + d["w42"]


def set_build(n: int) -> int:
    a = set(range(0, n, 2))
    b = set(range(0, n, 3))
    return len(a) + len(b)


def set_and(a: set[int], b: set[int]) -> int:
    return len(a & b) + len(a | b) + len(a - b)


def set_contains(c: set[int], n: int) -> int:
    t = 0
    for i in range(n):
        if i in c:
            t += 1
    return t


def str_set(words: list[str]) -> int:
    s: set[str] = set()
    for w in words:
        s.add(w)
    t = 0
    for w in words:
        if w in s:
            t += 1
    return t + len(s)


def main() -> None:
    n = 2000000
    t0 = time.perf_counter(); words = make_words(n); print(f"make_words\t{time.perf_counter() - t0:.4f}\t{len(words)}")
    t0 = time.perf_counter(); r = count_words(words); print(f"count_get\t{time.perf_counter() - t0:.4f}\t{r}")
    t0 = time.perf_counter(); r = count_words2(words); print(f"count_in\t{time.perf_counter() - t0:.4f}\t{r}")
    t0 = time.perf_counter(); r = set_build(3000000); print(f"set_build\t{time.perf_counter() - t0:.4f}\t{r}")
    a = set(range(0, 3000000, 2)); b = set(range(0, 3000000, 3))
    t0 = time.perf_counter(); r = set_and(a, b); print(f"set_and_or_sub\t{time.perf_counter() - t0:.4f}\t{r}")
    c = a & b
    t0 = time.perf_counter(); r = set_contains(c, 3000000); print(f"set_contains\t{time.perf_counter() - t0:.4f}\t{r}")
    t0 = time.perf_counter(); r = str_set(words); print(f"str_set\t{time.perf_counter() - t0:.4f}\t{r}")


main()
