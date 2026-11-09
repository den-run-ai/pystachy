import sys
import time


class Node:
    def __init__(self, k: int, name: str) -> None:
        self.k = k
        self.name = name
        self.w = 0.5


def peak_kb() -> int:
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmHWM:"):
                return int(line.split()[1])
    return -1


def churn(live: list[Node], rounds: int) -> int:
    t = 0
    for r in range(rounds):
        tmp = [Node(i, "t") for i in range(200000)]
        t += len(tmp) + tmp[r % 100].k
    return t + len(live)


def main(which: str) -> None:
    t0 = time.perf_counter()
    if which == "ints":
        xs = [i * 3 for i in range(5000000)]
        print(len(xs), xs[-1])
    elif which == "strs":
        ss = ["item" + str(i) for i in range(2000000)]
        print(len(ss), ss[-1])
    elif which == "dict":
        d = {"key" + str(i): i for i in range(2000000)}
        print(len(d), d["key77"])
    elif which == "objs":
        ns = [Node(i, "n") for i in range(3000000)]
        print(len(ns), ns[-1].k)
    elif which == "churn":
        live = [Node(i, "live" + str(i % 1000)) for i in range(3000000)]
        print(churn(live, 100))
    elif which == "floats":
        fs = [i * 0.5 for i in range(5000000)]
        print(len(fs), fs[-1])
    elif which == "tuples":
        ts = [(i, i + 1) for i in range(3000000)]
        print(len(ts), ts[-1])
    elif which == "intdict":
        di = {i: i * 2 for i in range(3000000)}
        print(len(di), di[77])
    elif which == "set":
        st = set(range(3000000))
        print(len(st), 77 in st)
    print(f"{which}\t{time.perf_counter() - t0:.3f}\t{peak_kb() // 1024}")


main(sys.argv[1])
