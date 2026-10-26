# pystachy: python-int
# Promoting ints (docs/python-int.md): bit_length(), bit_count(), bin(), hex(), oct(), format
# specifications and three-argument pow() of ints past 64 bits, as CPython gives them.


def value(i: int) -> int:
    # (values from a function: containers hold 64-bit ints, docs/python-int.md)
    if i == 0:
        return 0
    if i == 1:
        return -1
    if i == 2:
        return 255
    if i == 3:
        return 2 ** 63
    if i == 4:
        return -(2 ** 64) + 1
    if i == 5:
        return 3 ** 80
    if i == 6:
        return -(7 ** 45)
    return 2 ** 200 - 1


def fmt(v: int, spec: str) -> str:
    try:
        return format(v, spec)
    except ValueError as e:
        return "ValueError: " + str(e)
    except OverflowError as e:
        return "OverflowError: " + str(e)


for i in range(8):
    x = value(i)
    print(x.bit_length(), x.bit_count(), bin(x), hex(x), oct(x))
    print(f"{x:x}|{x:#X}|{x:,}|{x:_}|{x:_x}|{x:+}|{x: }|{x:n}|{x:#b}|{x:#o}")
    print(f"[{x:>70}][{x:<50}][{x:^52}][{x:=+60}][{x:060d}][{x:*^64,}]")
    print(fmt(x, "e"), fmt(x, ".3e"), fmt(x, "g"), fmt(x, ".2%"), ascii(fmt(x, "c")), fmt(x, "s"), fmt(x, ".2d"), fmt(x, "z"))

print(fmt(2 ** 5000, "d")[:56], fmt(2 ** 5000, "x")[:20], len(fmt(2 ** 5000, "b")), fmt(2 ** 1100, "e"))


def pw(a: int, b: int, m: int) -> str:
    try:
        return str(pow(a, b, m))
    except ValueError as e:
        return "ValueError: " + str(e)


big = 2 ** 127 - 1
print(pw(3, big - 1, big), pw(2 ** 100, 2 ** 100, 10 ** 30 + 7), pw(-(5 ** 50), 3, 2 ** 70), pw(5 ** 50, 3, -(2 ** 70)))
print(pw(7, -1, big), pw(7 ** 30, -3, 2 ** 89 - 1), pw(2 ** 70, -1, 2 ** 80), pw(2 ** 70, 5, 0), pw(2 ** 70, 0, 2 ** 65), pw(2 ** 70, 0, -(2 ** 65)))
print(pw(2 ** 70, 9, 1), pw(2 ** 70, 9, -1), pw(12345, 2 ** 70, 2 ** 64 + 13), pw(-3, 2 ** 70 + 1, 10 ** 25), pw(10, 25, 2 ** 64))


def pct(v: int) -> str:
    try:
        return "%d|%x|%#X|%o|%+d|%30d|%-30d|%030d|%e|%.3f|%r|%s" % (v, v, v, v, v, v, v, v, v, v, v, v)
    except OverflowError as e:
        return "OverflowError: " + str(e)


def pct_char(v: int) -> str:
    try:
        return "%c" % v
    except OverflowError as e:
        return "OverflowError: " + str(e)


for i in range(2, 8):
    print(pct(value(i)), "%d" % value(i), "%5x" % -value(i), pct_char(value(i)))
