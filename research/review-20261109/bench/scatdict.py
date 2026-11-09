import time


def rng(state: int) -> int:
    state ^= (state << 13) & 0xFFFFFFFFFFFF
    state ^= state >> 7
    state ^= (state << 17) & 0xFFFFFFFFFFFF
    return state & 0xFFFFFFFFFFFF


def run(n: int, mode: str) -> str:
    d: dict[int, int] = {}
    keys: list[int] = []
    s = 88172645463325252 & 0xFFFFFFFFFFFF
    for i in range(n):
        s = rng(s)
        if mode == "random":
            k = s
        elif mode == "shifted":
            k = i << 20
        elif mode == "stride":
            k = i * 4096 + 7
        else:
            k = i
        keys.append(k)
    t0 = time.perf_counter()
    for k in keys:
        d[k] = k
    t1 = time.perf_counter()
    t = 0
    for k in keys:
        t += d[k] & 1
    t2 = time.perf_counter()
    # shuffled order lookups
    idx = 0
    for i in range(n):
        s = rng(s)
        t += d[keys[s % n]] & 1
    t3 = time.perf_counter()
    return f"{mode:8} n={n}: insert {(t1 - t0) * 1e9 / n:6.1f} ns  in-order lookup {(t2 - t1) * 1e9 / n:6.1f} ns  shuffled lookup {(t3 - t2) * 1e9 / n:6.1f} ns  [{t % 1000}]"


def main() -> None:
    for mode in ["seq", "random", "shifted", "stride"]:
        print(run(2000000, mode))


main()
