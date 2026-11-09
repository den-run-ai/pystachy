import time


def b_eq(ws: list[str], n: int) -> int:
    t = 0
    for r in range(n):
        for i in range(1, len(ws)):
            if ws[i] == ws[i - 1]:
                t += 1
            if ws[i] != "word00042":
                t += 2
    return t


def b_kind(kinds: list[str], n: int) -> int:
    t = 0
    for r in range(n):
        for k in kinds:
            if k == "error" or k == "stop":
                t += 1
            elif k == "?":
                t += 2
            elif k == "name":
                t += 3
    return t


def main() -> None:
    ws = ["word%05d" % ((i * 7919) % 10007) for i in range(1000)]
    kinds = ["name", "op", "number", "string", "newline", "indent", "name", "op"] * 125
    t0 = time.perf_counter(); r = b_eq(ws, 20000); print(f"str_eq\t{time.perf_counter() - t0:.4f}\t{r}")
    t0 = time.perf_counter(); r = b_kind(kinds, 20000); print(f"kind_eq\t{time.perf_counter() - t0:.4f}\t{r}")


main()
