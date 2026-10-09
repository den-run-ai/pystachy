# dict lookups of ordinary keys, on their own: sequential int keys and short str keys, in tables
# that fit in the cache (1k and 30k keys) and in tables that do not (1M int keys, 300k str keys);
# each dict is filled once, looked up a few million times and probed once for each absent key
# (bench/dictkeys.py times keys that collide)


def int_rounds(n: int, rounds: int) -> None:
    d: dict[int, int] = {}
    for i in range(n):
        d[i] = i
    s = 0
    for r in range(rounds):
        for i in range(n):
            s += d[i]
    absent = 0
    for i in range(n, 2 * n):
        if i in d:
            absent += 1
    print(f"int {n:>8} x {rounds:>4}: {s} {absent}")


def str_rounds(n: int, rounds: int) -> None:
    ks: list[str] = []
    for i in range(n):
        ks.append("w" + str(i))
    d: dict[str, int] = {}
    for i in range(n):
        d[ks[i]] = i
    s = 0
    for r in range(rounds):
        for k in ks:
            s += d[k]
    absent = 0
    for i in range(n):
        if "v" + str(i) in d:
            absent += 1
    print(f"str {n:>8} x {rounds:>4}: {s} {absent}")


int_rounds(1000, 2000)
int_rounds(30000, 70)
int_rounds(1000000, 8)
str_rounds(1000, 1000)
str_rounds(30000, 35)
str_rounds(300000, 6)
