# pystachy: python-int
import sys
import math

STATE = 0x9E3779B97F4A7C15


def rnd() -> int:
    global STATE
    STATE = (STATE * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
    x = STATE
    x ^= x >> 33
    x = (x * 0xFF51AFD7ED558CCD) & 0xFFFFFFFFFFFFFFFF
    x ^= x >> 33
    return x


def operand() -> int:
    k = rnd() % 12
    v = rnd()
    if k == 0:
        return v % 7 - 3
    if k == 1:
        return (1 << 63) - (v % 5) + 2
    if k == 2:
        return -(1 << 63) + (v % 5) - 2
    if k == 3:
        return (1 << 64) + (v % 7) - 3
    if k == 4:
        return v | (rnd() << 64)
    if k == 5:
        return -(v | (rnd() << 64) | (rnd() << 128))
    if k == 6:
        return 1 << (v % 200)
    if k == 7:
        return -(1 << (v % 200)) + (rnd() % 3 - 1)
    if k == 8:
        return (v % 2000003) - 1000001
    if k == 9:
        return v - (1 << 63)
    if k == 10:
        return (v * rnd() * rnd()) >> (rnd() % 100)
    return 10 ** (v % 40) + (rnd() % 3 - 1)


def check(n: int) -> None:
    for i in range(n):
        a = operand()
        b = operand()
        c = operand()
        out: list[str] = [str(i), str(a), str(b)]
        out.append(str(a + b))
        out.append(str(a - b))
        out.append(str(a * b))
        if b != 0:
            out.append(str(a // b))
            out.append(str(a % b))
            q, r = divmod(a, b)
            out.append(str(q * b + r == a))
            out.append(repr(a / b) if abs(a) < 10**300 and abs(b) < 10**300 else "big")
        out.append(str(a & b))
        out.append(str(a | b))
        out.append(str(a ^ b))
        out.append(str(~a))
        out.append(str(-a))
        out.append(str(abs(a)))
        sh = rnd() % 130
        out.append(str(a << sh))
        out.append(str(a >> sh))
        out.append(str((a < b, a <= b, a == b, a != b, a > b, a >= b)))
        out.append(str(a.bit_length()))
        out.append(hex(a))
        out.append(bin(b)[:40])
        out.append(oct(c))
        out.append(str(hash(a)))
        e = rnd() % 6
        out.append(str(a**e))
        if c != 0:
            out.append(str(pow(a, e + 3, c)))
        out.append(repr(float(a)) if abs(a) < 10**300 else "big")
        out.append(str(int(str(a)) == a))
        out.append(str(int(hex(a), 16) == a))
        out.append(f"{a:,}" + f"{b:x}" + f"{c:+d}" + f"{a:#b}"[:30] + f"{b:>40}" + f"{c:_}")
        out.append(str(min(a, b, c)) + str(max(a, b, c)))
        out.append(str(sum([a, b, c])))
        out.append(str(sorted([a, b, c, -a, a + 1, a - 1])))
        out.append(str(int(a / 3) if abs(a) < 2**52 else 0))
        out.append(str(a == float(a)) if abs(a) < 10**300 else "big")
        out.append(str((a < 1e30, a > -1e30, a == 2.0**70, a < float("inf"), a > float("nan"))))
        out.append(str(a * 1.5) if abs(a) < 10**300 else "big")
        out.append(str(a + 0.5) if abs(a) < 10**300 else "big")
        out.append(str(divmod(a, 7)) + str(divmod(a, -7)) + str(a % 2**64) + str(a // 2**64))
        d = {a: 1, b: 2, c: 3}
        out.append(str(d[a] + d.get(b + 0, 0) + len(d)) + str(a in d) + str(a + 1 in d))
        s = {a, b, c, a + 0, b * 1}
        out.append(str(len(s)) + str(sorted(s)[0]))
        print("|".join(out))


check(400 + len(sys.argv) - 1)
