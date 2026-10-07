# Arbitrary-precision arithmetic on lists of decimal digits, least significant first.


def from_int(n: int) -> list[int]:
    d: list[int] = []
    while n > 0:
        d.append(n % 10)
        n = n // 10
    return d


def show(a: list[int]) -> str:
    if len(a) == 0:
        return "0"
    s = ""
    i = len(a) - 1
    while i >= 0:
        s = s + str(a[i])
        i -= 1
    return s


def add(a: list[int], b: list[int]) -> list[int]:
    out: list[int] = []
    carry = 0
    for i in range(max(len(a), len(b))):
        t = carry
        if i < len(a):
            t += a[i]
        if i < len(b):
            t += b[i]
        out.append(t % 10)
        carry = t // 10
    if carry > 0:
        out.append(carry)
    return out


def mul_small(a: list[int], k: int) -> list[int]:
    out: list[int] = []
    carry = 0
    for d in a:
        t = d * k + carry
        out.append(t % 10)
        carry = t // 10
    while carry > 0:
        out.append(carry % 10)
        carry = carry // 10
    return out


def mul(a: list[int], b: list[int]) -> list[int]:
    out = [0] * (len(a) + len(b))
    for i in range(len(a)):
        carry = 0
        for j in range(len(b)):
            t = out[i + j] + a[i] * b[j] + carry
            out[i + j] = t % 10
            carry = t // 10
        out[i + len(b)] += carry
    while len(out) > 0 and out[-1] == 0:
        out.pop()
    return out


def digit_sum(a: list[int]) -> int:
    t = 0
    for d in a:
        t += d
    return t


f = from_int(1)
for n in range(2, 101):
    f = mul_small(f, n)
print(show(f))
print(len(f), digit_sum(f))
a = from_int(0)
b = from_int(1)
for n in range(500):
    c = add(a, b)
    a = b
    b = c
print(show(a))
p = from_int(1)
big = from_int(9223372036854775807 // 3)
for n in range(5):
    p = mul(p, big)
print(show(p), show(mul(from_int(0), p)), show(mul(from_int(12345), from_int(6789))))
