# int(s, base) at the ends of the 64-bit range, in every base. The largest and the least int are
# read; the next value past each is too large for an int here (OverflowError), where CPython
# has an int for it: both print "big". A str that is no int is a ValueError first
DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"
MAXI = 9223372036854775807


def spell(v: int, base: int) -> str:
    out = ""
    while True:
        out = DIGITS[v % base] + out
        v //= base
        if v == 0:
            return out


def succ(s: str, base: int) -> str:
    # the digits of the next integer
    i = len(s) - 1
    out = ""
    while i >= 0 and DIGITS.index(s[i]) == base - 1:
        out = "0" + out
        i -= 1
    if i < 0:
        return "1" + out
    return s[:i] + DIGITS[DIGITS.index(s[i]) + 1] + out


def read(s: str, base: int) -> str:
    try:
        v = int(s, base)
    except OverflowError:
        return "big"
    return str(v) if -MAXI - 1 <= v <= MAXI else "big"


for base in range(2, 37):
    top = spell(MAXI, base)
    over = succ(top, base)  # 2**63
    under = spell(MAXI // base, base)  # the digits before the last
    out = [read(top, base), read(over, base), read("-" + top, base), read("-" + over, base), read("-" + succ(over, base), base),
           read(top + "0", base), read("-" + top + "0", base), read(under + DIGITS[base - 1], base), read(succ(under, base) + "0", base),
           read("+" + top.upper(), base), read("0" * 40 + top, base), read(" " + top[0] + "_" + top[1:] + "\n", base)]
    print(base, top, " ".join(out))
for pre, base in [("0x", 16), ("0o", 8), ("0b", 2)]:
    top = spell(MAXI, base)
    over = succ(top, base)
    print(pre, read(pre + top, 0), read(pre + over, 0), read("-" + pre + over, 0), read("-" + pre + succ(over, base), 0),
          read(pre.upper() + "_" + top, base), read("-" + pre.upper() + over, base))
for s, base in [("9" * 30, 10), ("-" + "9" * 30, 10), ("1" + "0" * 64, 2), ("-1" + "0" * 63, 2), ("z" * 20, 36), ("9" * 30 + "x", 10),
                ("9" * 30 + " ", 10), ("9" * 30 + "_", 10), ("0" + "9" * 30, 0), ("9" * 30 + "\x00", 10), ("9" * 30 + "٩", 10)]:
    try:
        print(len(s), base, read(s, base))
    except ValueError as e:
        print(len(s), base, "ValueError", str(e)[:64])
