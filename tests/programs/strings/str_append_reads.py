# strs that appends in place (#112) grow past 8,200 bytes, where a copy is a large object (#567),
# while the program reads them between appends: s[-2] every k appends, endswith() after a few,
# a helper that appends to its parameter and returns it, a str built and then read once (s[-1],
# return s). Then kept strs that live through collections (the collector gives back the room
# that their last copy left, once they stop growing) and grow again, and a str a local still
# appends to after collections ran while it waited.


def periodic(n: int, k: int) -> int:
    s = ""
    tot = 0
    for i in range(n):
        s += "%07d," % i
        if i % k == 0:
            tot += ord(s[-2]) + len(s)
    return tot + len(s) + s.count("9,")


def ends(n: int) -> str:
    out = ""
    for i in range(n):
        out += "item "
        out += str(i)
        out += ";"
        if out.endswith("0;"):
            out += "\n"
    return out


def emit(out: str, x: int) -> str:
    out += "<td>"
    out += str(x)
    out += "</td>"
    return out


def table(n: int) -> str:
    out = ""
    for i in range(n):
        out = emit(out, i)
        out += "\n"
    return out


def build(n: int) -> str:
    s = ""
    for _ in range(n):
        s += "abcdefgh"
    return s


def last(n: int) -> int:
    s = ""
    for _ in range(n):
        s += "abcdefgh"
    return len(s) + ord(s[-1])


def grow(n: int, piece: str) -> str:
    s = ""
    for _ in range(n):
        s += piece
    return s


def churn(mb: int) -> int:
    # about mb MiB of garbage: past 32 MiB a collection runs
    t = 0
    for i in range(mb):
        b = str(i % 10) * (1 << 20)
        t += ord(b[i * 1000])
    return t


def reads() -> None:
    print([periodic(3000, k) for k in (1, 2, 3, 5, 10, 700)])
    e = ends(3000)
    print(len(e), e.count("\n"), e[:12], e[-12:], e[8190:8210])
    t = table(2500)
    print(len(t), t.count("\n"), t[-20:], t[16380:16400])
    for n in (1020, 1100, 2047, 2049, 3000, 5000, 20000):
        s = build(n)
        print(n, len(s), s[-3:], last(n), s == "abcdefgh" * n)


def kept() -> None:
    out: list[str] = []
    for i in range(80):
        out.append(grow(200 + 61 * i, "%07d|" % i))
    print(churn(70))
    total = 0
    for i in range(len(out)):
        x = out[i]
        total += len(x) + ord(x[-2]) + x.count("|")
        if x != ("%07d|" % i) * (200 + 61 * i):
            print("bad", i)
    print(len(out), total, out[5][:9], out[-1][-9:], out[40][8195:8205])
    print(sorted([len(x) for x in out])[-3:], out[30] < out[31], out[12][::4096][:5])
    again: list[str] = []
    for i in range(0, 80, 9):
        y = out[i]  # (not owned: the first append copies it)
        for j in range(300):
            y += "+%d" % (j % 7)
        again.append(y)
        print(i, len(y), y[: len(out[i])] == out[i], y[-6:], out[i][-6:])
    print(churn(40), [len(a) for a in again][:4], again[3][-4:])


def waits() -> None:
    s = grow(5000, "abc|")  # (a local that appends grew: a collection may give back its room)
    s += "x"
    s += "y"  # (owned now: a copy with room)
    print(churn(70))
    for i in range(4000):
        s += "%d;" % (i % 10)
    print(len(s), s[19995:20010], s[-8:], s.count("|"), s.count(";"))
    print(churn(40))
    s += "end"
    print(len(s), s[-6:])


reads()
kept()
waits()
