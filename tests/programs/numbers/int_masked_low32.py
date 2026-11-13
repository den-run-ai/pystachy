# x & y with a constant from 0 to 2**32 - 1 on a side and, on the other, ints alone under +, -,
# *, &, |, ^, << and >> by literal counts: the compiler computes the low 32 bits as 32-bit values,
# and (x << c) | (x >> (32 - c)) as a rotation of x's low 32 bits with the bits that the right
# shift brings down from above them. The result must be CPython's for every int, not only for
# the values below 2**32 that hash code rotates. The values are read from a list at run time.

MASK = 0xFFFFFFFF
K0 = 0x5A827999
WIDE = 0x100000000  # (one past the masks that are computed in 32 bits)


def rotations(x: int) -> list[int]:
    return [
        ((x << 5) | (x >> 27)) & 0xFFFFFFFF,
        ((x >> 2) | (x << 30)) & MASK,
        MASK & ((x << 1) | (x >> 31)),
        0xFFFFFFFF & ((x >> 31) | (x << 1)),
        ((x << 31) | (x >> 1)) & 0xFFFF,
        ((x << 16) | (x >> 16)) & 0xFF00FF00,
        ((x << 13) | (x >> 19)) & 1,
        ((x << 13) | (x >> 19)) & 0,
        ((x << 7) | (x >> 25)) & WIDE,
        ((x << 7) | (x >> 25)) & 0x1FFFFFFFF,
        ((x << 7) | (x >> 24)) & MASK,
        ((x << 7) + (x >> 25)) & MASK,
        ((x << 7) ^ (x >> 25)) & MASK,
    ]


def mixed(x: int, y: int) -> list[int]:
    return [
        ((x << 5) | (y >> 27)) & MASK,
        (((x << 7) | (x >> 25)) ^ ((x >> 13) | (x << 19)) ^ (x >> 3)) & MASK,
        (((x >> 6) | (x << 26)) ^ ((y >> 11) | (y << 21)) ^ ((x >> 25) | (x << 7))) & MASK,
        ((((x << 5) | (x >> 27)) & 0xFFFFFFFF) + ((x & y) | ((x ^ 0xFFFFFFFF) & K0)) + y + 0x5A827999 + x) & 0xFFFFFFFF,
        (x * y - x + (y << 3) - (x >> 60)) & MASK,
        (x * 0xCC9E2D51 + K0) & MASK,
        (x - y) & 0xFFFFFFFF,
        (x + y) & 0xFF,
        (x >> 0) & MASK,
        (x >> 32) & MASK,
        (x >> 63) & MASK,
        ((x << 0) | (y << 31)) & MASK,
        ((x & 0xFF00) | (y & 0xFF)) & 0xFFFF,
        (x ^ y ^ MASK) & MASK,
        ((x + y) & MASK) + ((x - y) & MASK),
        (x + y + 9223372036854775807) & MASK,
        (x * x * y * 4294967295) & 0xFFFFFFFF,
    ]


def other_types(flag: bool, x: int) -> list[int]:
    # (a bool rotates as the int it is; an operand that is no plain int keeps the 64-bit steps)
    return [((flag << 3) | (flag >> 29)) & MASK, ((x << 3) | (flag >> 29)) & MASK, (flag + x) & 0xFF]


def narrowed(x: int | None) -> int:
    if x is not None:
        return ((x << 5) | (x >> 27)) & 0xFFFFFFFF
    return -1


def loop_variable(n: int) -> int:
    t = 0
    for i in range(n):
        t ^= ((i << 7) | (i >> 25)) & MASK
        t = (t + i * 0x9E3779B1) & MASK
    return t


def comprehension(vs: list[int]) -> list[int]:
    return [((v << 30) | (v >> 2)) & 0xFFFFFFFF for v in vs]


def default(x: int = 0x80000000) -> int:
    return ((x << 1) | (x >> 31)) & MASK


def augmented(x: int) -> int:
    x = x * 33 & MASK
    x ^= (x << 13) & MASK
    return x


def unbound(c: bool) -> int:
    if c:
        y = 0x80000001
    try:
        return ((y << 5) | (y >> 27)) & 0xFFFFFFFF
    except UnboundLocalError:
        return -1


def late(x: int) -> int:
    return (x + 1) & LATE


def late_first(x: int) -> int:
    return LATE & ((x << 9) | (x >> 23))


def sha1_round(a: int, b: int, c: int, d: int, e: int, w: int) -> list[int]:
    e = ((((a << 5) | (a >> 27)) & 0xFFFFFFFF) + ((b & c) | ((b ^ 0xFFFFFFFF) & d)) + e + 0x5A827999 + w) & 0xFFFFFFFF
    b = ((b << 30) | (b >> 2)) & 0xFFFFFFFF
    x = a ^ c ^ d ^ w
    w = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
    return [e, b, w]


def values() -> list[int]:
    vs = [0, 1, 2, 3, 31, 32, 255, 65535, 2147483647, 2147483648, 4294967295, 4294967296, 4294967297,
          1311768467294899695, 9223372036854775807, -1, -2, -2147483648, -2147483649, -4294967296,
          -9223372036854775808, 123456789012345, -987654321098765]
    s = 88172645463325252
    for _ in range(40):
        s = (s * 6364136223846793005 + 1442695040888963407) & 0x7FFFFFFFFFFFFFFF
        vs.append(s - (1 << 62))
        vs.append(s & 0xFFFFFFFF)
    return vs


def main() -> None:
    vs = values()
    total = 0
    for i in range(len(vs)):
        x = vs[i]
        y = vs[(i * 7 + 3) % len(vs)]
        row = rotations(x) + mixed(x, y) + other_types(x % 2 == 0, y) + sha1_round(x, y, vs[(i + 1) % len(vs)], vs[(i + 5) % len(vs)], vs[(i + 11) % len(vs)], y)
        for r in row:
            total = (total * 1000003 + r) & 0x3FFFFFFFFFFFFFFF
        if i < 23:
            print(x, row)
    print(total)
    print(unbound(True), unbound(False))
    print(narrowed(vs[13]), narrowed(vs[20]), narrowed(None), loop_variable(50), comprehension(vs[9:14]), default(), default(vs[19]))
    print([augmented(v) for v in vs[8:16]])
    try:
        print(late(5))
    except NameError as e:
        print("NameError:", e)
    try:
        print(late_first(5))
    except NameError as e:
        print("NameError:", e)


main()
LATE = 0xFFFF
print(late(0x12345), late_first(0x12345678))
