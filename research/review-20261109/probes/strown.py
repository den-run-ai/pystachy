import sys


def a1(n: int) -> list[str]:
    s = ""
    parts: list[str] = []
    for i in range(n):
        s += "ab"
        parts.append(s)
    return parts


def a2(n: int) -> None:
    s = "x"
    s += "y" * n
    t = s[:]
    u = s.strip()
    v = str(s)
    w = s.replace("q", "r")
    x = "".join([s])
    y = s * 1
    z = f"{s}"
    s += "TAIL" * n
    print(len(t), len(u), len(v), len(w), len(x), len(y), len(z), len(s))
    print(t == u == v == w == x == y == z, t.endswith("y"), s.endswith("TAIL"))


def a3(n: int) -> None:
    s = ""
    seen: dict[str, int] = {}
    for i in range(n):
        s += chr(97 + i % 26)
        seen[s] = i
        s += "!"
    print(len(seen), sorted(seen.items())[:3], s[:20])
    keys = list(seen)
    print(all(seen[k] == j for j, k in enumerate(keys)), keys[2])


def a4(n: int) -> None:
    s = ""

    def peek() -> str:
        return s

    held: list[str] = []
    for i in range(n):
        s += "z"
        held.append(peek())
    print(held)


def a5(n: int):
    s = ""
    for i in range(n):
        s += str(i)
        yield s
        s += ","


def a6(n: int) -> None:
    s = "é"
    out: list[int] = []
    for i in range(n):
        s += "ü"
        out.append(len(s))
        k = len(s)
        s += "a" * 30
        c = s[k - 1]
        s += "ß"
        out.append(ord(c))
        out.append(ord(s[-1]))
    print(out, len(s))


def a7(n: int) -> None:
    class_like: list[tuple[str, int]] = []
    s = ""
    for i in range(n):
        s += "k"
        class_like.append((s, i))
        s = s + "m"
        t = (s, i)
        s += "n"
        class_like.append(t)
    print(class_like)


def a8(n: int) -> None:
    s = ""
    last = ""
    for i in range(n):
        s += "p" * 40
        if (cur := s) and i == 1:
            last = cur
        s += "q" * 40
    print(len(last), last.count("q"), last.count("p"))


n = len(sys.argv) + 3
print(a1(n))
a2(n)
a3(n * 10)
a4(n)
print(list(a5(n)))
a6(n)
a7(3)
a8(4)
