# dict hashing: int keys that differ only in their high bits (i << 46 once piled up in one
# cluster), spaced or packed int keys, str keys sharing a long prefix or suffix or differing only
# in letter case, and sequential keys as the control, at 4k, 8k, 16k and 30k keys; checksums of
# the values and of the iteration order after deletions, reinsertions and copies
# (tools/dictprobe.c counts the table slots that such keys visit)
M = 1000000007


def int_keys(kind: int, n: int) -> list[int]:
    ks: list[int] = []
    for i in range(n):
        if kind == 0:
            ks.append(i)
        elif kind == 1:
            ks.append(i << 46)
        elif kind == 2:
            ks.append(i << 32)
        elif kind == 3:
            ks.append(-i * 1000)
        else:
            ks.append((i // 128) << 32 | i % 128)
    return ks


def str_keys(kind: int, n: int) -> list[str]:
    ks: list[str] = []
    for i in range(n):
        if kind == 0:
            ks.append(f"k{i}")
        elif kind == 1:
            ks.append("x" * 64 + str(i))
        elif kind == 2:
            ks.append(str(i) + "x" * 64)
        else:
            ks.append("".join([chr(97 + j - 32 * (i >> j & 1)) for j in range(20)]))
    return ks


def rounds(name: str, ks) -> None:
    # the first half of ks goes into the dict; the second half stays absent
    n = len(ks) // 2
    d = {}
    for i in range(n):
        d[ks[i]] = i
    s = 0
    for i in range(n):
        s = (s * 31 + d[ks[i]]) % M
    absent = 0
    for i in range(n, 2 * n):
        if ks[i] in d:
            absent += 1
        s = (s * 31 + d.get(ks[i], 7)) % M
    for i in range(0, n, 2):
        del d[ks[i]]
    for i in range(1, n, 4):
        s = (s * 31 + d.pop(ks[i]) + d.pop(ks[i - 1], 5)) % M
    for i in range(n - 1, -1, -3):
        s = (s * 31 + d.setdefault(ks[i], -i)) % M
    c = dict(d)
    for i in range(n, 2 * n, 2):
        c[ks[i]] = i
    order = 0
    for k, v in c.items():
        order = (order * 31 + v) % M
    for k in d:
        order = (order * 31 + c[k]) % M
    print(f"{name:<14} {n:>6} {len(d):>6} {len(c):>6} {absent} {s:>10} {order:>10} {c == d} {d == d.copy()}")


for n in [4000, 8000, 16000, 30000]:
    names = ["i", "i << 46", "i << 32", "-i * 1000", "packed pairs"]
    for kind in range(len(names)):
        rounds(names[kind], int_keys(kind, 2 * n))
    names = ["f'k{i}'", "'x' * 64 + i", "i + 'x' * 64", "letter case"]
    for kind in range(len(names)):
        rounds(names[kind], str_keys(kind, 2 * n))
