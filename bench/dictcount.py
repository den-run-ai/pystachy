# dict counting in the shapes that look one key up two or three times: if k in d: d[k] += 1,
# if k in d: v = d[k], and d[k] = d[k] + 1, over short str keys and int keys (dictfuse, in
# docs/typed-ir.md 7.1, makes each one lookup)
def words(n: int, distinct: int) -> list[str]:
    ws: list[str] = []
    seed = 7
    for i in range(n):
        seed = (seed * 1103515245 + 12345) % 2147483648
        ws.append("w" + str(seed % distinct))
    return ws


def count(ws: list[str], rounds: int) -> dict[str, int]:
    d: dict[str, int] = {}
    for r in range(rounds):
        for w in ws:
            if w in d:
                d[w] += 1
            else:
                d[w] = 1
    return d


def known(ws: list[str], d: dict[str, int]) -> int:
    s = 0
    for w in ws:
        if w in d:
            v = d[w]
            s += v % 7
    return s


def bump(n: int, rounds: int) -> int:
    d: dict[int, int] = {}
    for i in range(n):
        d[i * 7919 % n] = 0
    for r in range(rounds):
        for i in range(n):
            d[i] = d[i] + r
    return d[n - 1]


ws = words(200000, 5000)
d = count(ws, 20)
print(len(d), d["w0"], d["w4999"], max(d.values()))
print(known(words(200000, 10000), d))
print(bump(50000, 80))
