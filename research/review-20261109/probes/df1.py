import sys


class K:
    def __init__(self, v: int, log: list[str]) -> None:
        self.v = v
        self.log = log

    def __hash__(self) -> int:
        self.log.append(f"h{self.v}")
        return self.v % 4

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, K):
            return False
        self.log.append(f"e{self.v}:{other.v}")
        return self.v == other.v


def run(label: str, f) -> None:
    try:
        print(label, f())
    except Exception as e:
        print(label, type(e).__name__, e)


def d1(d: dict[str, int], k: str, other: list[str]) -> int:
    if k in d:
        for o in other:
            d[o] = 5
        d[k] += 1
    return d[k]


def d2(d: dict[str, int], e: dict[str, int], k: str) -> int:
    if k in d:
        e.pop(k)
        return d[k]
    return -1


def d3(d: dict[str, int], k: str, k2: str) -> int:
    if k in d:
        k = k2
        return d[k]
    return -1


def d4(d: dict[str, int], d2_: dict[str, int], k: str) -> int:
    if k in d:
        d = d2_
        return d[k]
    return -1


def d5(d: dict[int, int], n: int) -> int:
    t = 0
    for i in range(n):
        if i in d:
            d[i] += 1
            del d[i]
            if i in d:
                t += 1000
            d[i] = 7
            t += d[i]
        else:
            d[i] = 1
            d[i] += d.get(i, 100)
            t += d[i]
    return t


def d6(d: dict[str, list[int]], k: str) -> list[int]:
    if k not in d:
        d[k] = []
    d[k].append(1)
    d.clear()
    d.setdefault(k, []).append(2)
    return d[k]


def d7(log: list[str]) -> list[str]:
    d: dict[K, int] = {}
    a = K(1, log)
    b = K(5, log)
    d[a] = 1
    log.append("|")
    if b in d:
        log.append("yes")
    log.append("|")
    d[b] = d.get(b, 0) + 1
    log.append("|")
    if a in d:
        d[a] += 1
    log.append("|")
    d[a] = d[a] + d[b]
    return log


def d8(d: dict[str, int], k: str) -> int:
    v = d.get(k)
    if v is None:
        d[k] = 0
    d[k] += 1
    x = d[k]
    d.pop(k)
    d[k] = 100
    return x + d[k]


def d9(d: dict[tuple[int, int], int], n: int) -> int:
    t = 0
    for i in range(n):
        key = (i % 3, i % 2)
        if key in d:
            d[key] += i
        else:
            d[key] = i
        if d[key] > 6:
            d.pop(key)
            d[(9, i)] = 1
        t += len(d)
    return t


class Box:
    def __init__(self) -> None:
        self.d: dict[str, int] = {"a": 1}

    def swap(self) -> None:
        self.d = {"b": 2}


def d10(b: Box) -> int:
    if "a" in b.d:
        b.swap()
        return b.d["a"]
    return -1


def d11(d: dict[str, int]) -> int:
    t = 0
    for k in list(d):
        if k in d:
            for j in range(40):
                d[k + str(j)] = j
            t += d[k]
            d[k] += 1
            t += d[k]
    return t


def d12(d: dict[int, str], k: int) -> str:
    if k in d and d[k] == "x":
        d[k] = d[k] + "y"
        d[k + 1] = "n"
        d[k] += d[k + 1]
    return d.get(k, "?") + str(len(d))


def main(n: int) -> None:
    run("d1", lambda: d1({"a": 1}, "a", [str(i) for i in range(100 + n)]))
    dd = {"a": 1, "b": 2}
    run("d2", lambda: d2(dd, dd, "a"))
    run("d3", lambda: d3({"a": 1}, "a", "zz"))
    run("d4", lambda: d4({"a": 1}, {"b": 1}, "a"))
    run("d5", lambda: d5({1: 1, 3: 3}, 6 + n))
    run("d6", lambda: d6({}, "k"))
    run("d7", lambda: d7([]))
    run("d8", lambda: d8({}, "q"))
    run("d9", lambda: d9({}, 20 + n))
    run("d10", lambda: d10(Box()))
    run("d11", lambda: d11({"x": 1, "y": 2}))
    run("d12", lambda: d12({1: "x"}, 1))


main(len(sys.argv) - 1)
