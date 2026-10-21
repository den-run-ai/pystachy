# s += t and s = s + t of a str local append in place to a str that only the local holds (#112):
# appending in a loop is linear. Loops, both branches, try statements, a parameter or a constant
# as the first value, strs kept between appends as they grow through size classes and past the
# allocator's largest (8200 bytes), where a copy leaves room.


def build(n: int) -> str:
    out = ""
    for i in range(n):
        out += "| row %6d |\n" % i
    return out


def plus(n: int) -> str:
    s = "<"
    for i in range(n):
        s = s + str(i % 10)
    s = s + ">"
    return s


def branches(n: int) -> str:
    s = "start:"
    for i in range(n):
        if i % 3 == 0:
            s += "a"
        else:
            s += "bc"
            s += str(i)
    return s


def param(s: str, n: int) -> str:
    for i in range(n):
        s += "-%d" % i
    return s


def guarded(n: int) -> str:
    s = ""
    for i in range(n):
        try:
            s += str(12 // (i - 3))
            s += ","
        except ZeroDivisionError:
            s += "Z,"
    try:
        s += "end"
        raise ValueError(s)
    except ValueError as e:
        s += "|" + str(e)
    return s


def nested(rows: list[str]) -> str:
    out = ""
    sep = "+" + "-" * 10 + "+\n"
    out += sep
    for r in rows:
        line = "|"
        for c in r:
            line += " " + c
        out += line.ljust(11) + "|\n"
        out += sep
    return out


def big(n: int, piece: str) -> str:
    s = ""
    for i in range(n):
        s += piece
        s += str(i)
    return s


def checksum(s: str) -> int:
    h = 0
    for c in s:
        h = (h * 31 + ord(c)) % 1000000007
    return h


def until(limit: int) -> str:
    s = "x"
    while len(s) < limit:
        s += "y" if len(s) % 7 == 0 else "x"
    return s


def around(start: int, n: int) -> list[str]:
    out: list[str] = []
    s = "a" * start
    for i in range(n):
        s += str(i % 10) * 3
        if i % 4 == 3:
            out.append(s)
    return out


b = build(2000)
print(len(b), checksum(b), b[:30], b[-15:])
print(plus(25))
print(branches(10))
p = "p"
print(param(p, 5), p)
print(param("const", 3))
print(guarded(7))
print(nested(["ab", "cde", ""]), end="")
g = big(5000, "0123456789abcdef")
print(len(g), checksum(g), g[8190:8215], g[-20:])
print(until(30), len(until(20000)))
lines = [build(i) for i in range(4)]
print(lines)
print([(len(x), x[-7:]) for x in around(240, 40)])
print([(len(x), x[-7:]) for x in around(8170, 40)])
