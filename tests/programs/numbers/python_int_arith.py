# pystachy: python-int
# Promoting ints (docs/python-int.md): every int operator on operands around the 64-bit edges, as
# CPython computes it. Results past 64 bits promote, and results that fit come back to 64 bits.

MAX = 9223372036854775807
MIN = -9223372036854775808
N = 20


def value(i: int) -> int:
    # (operands come from a function: until containers hold promoting ints, a list's items are
    # 64-bit, docs/python-int.md)
    if i < 7:
        return [0, 1, -1, 2, -2, 7, -7][i]
    if i == 7:
        return 2 ** 31
    if i == 8:
        return MAX
    if i == 9:
        return MIN
    if i == 10:
        return MAX - 1
    if i == 11:
        return MIN + 1
    if i == 12:
        return MAX + 1
    if i == 13:
        return MIN - 1
    if i == 14:
        return 2 ** 64
    if i == 15:
        return -(2 ** 64)
    if i == 16:
        return 3 ** 50
    if i == 17:
        return -(5 ** 40)
    if i == 18:
        return 2 ** 100 + 12345
    return -(2 ** 100) - 54321


def row(op: str, a: int) -> list[str]:
    out: list[str] = []
    for j in range(N):
        b = value(j)
        if op == "+":
            out.append(str(a + b))
        elif op == "-":
            out.append(str(a - b))
        elif op == "*":
            out.append(str(a * b))
        elif op == "//":
            out.append(str(a // b) if b != 0 else "-")
        elif op == "%":
            out.append(str(a % b) if b != 0 else "-")
        elif op == "&":
            out.append(str(a & b))
        elif op == "|":
            out.append(str(a | b))
        else:
            out.append(str(a ^ b))
    return out


for op in ["+", "-", "*", "//", "%", "&", "|", "^"]:
    for i in range(N):
        print(op, value(i), " ".join(row(op, value(i))))

for i in range(N):
    a = value(i)
    print("unary", a, -a, +a, ~a, abs(a), a == -(-a))

COUNTS = [0, 1, 5, 31, 62, 63, 64, 65, 100, 200]
for i in range(N):
    a = value(i)
    print("<<", a, " ".join([str(a << c) for c in COUNTS]))
    print(">>", a, " ".join([str(a >> c) for c in COUNTS]))
    print("back", a, " ".join([str((a << c) >> c == a) for c in COUNTS]))

for b in [-3, -2, -1, 0, 1, 2, 3, 10, 2 ** 40, -(2 ** 40)]:
    print("**", b, " ".join([str(b ** e) for e in [0, 1, 2, 5, 13, 31, 63, 64, 65, 100]]))
print((-1) ** (2 ** 70), (-1) ** (2 ** 70 + 1), 0 ** (2 ** 70), 1 ** (2 ** 70), pow(-2, 63), pow(2, 64))

# demotion: results that fit are 64-bit again, and keep working with 64-bit operands
x = MAX + 10
y = x - 20
print(y, y + 1, y * 0, y // 3, (x * x) // x == x, (x * x) % x, x - x, (x * 3) - (x * 2) == x)
z = MIN - 1
print(z + 1 == MIN, -z, -MIN, MIN // -1, MIN % -1, MIN * -1)

# augmented assignment, mixed with bool
acc = MAX
acc += True
acc *= 3
acc -= MAX * 3
acc //= 2
acc **= 2
print(acc, True + MAX, MIN - True, (MAX + 1) * False, -True)


def fact(n: int) -> int:
    r = 1
    for i in range(2, n + 1):
        r *= i
    return r


def fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


print(fact(25), fact(60) // fact(58), fib(93), fib(94), fib(300) % 1000000007)
s = 0
for i in range(100):
    s += 3 ** i
print(s, s % 997, s >> 150)

try:
    print(5 // 0)
except ZeroDivisionError as e:
    print("ZeroDivisionError:", e)
try:
    print((2 ** 70) % 0)
except ZeroDivisionError as e:
    print("ZeroDivisionError:", e)
try:
    print(1 << -1)
except ValueError as e:
    print("ValueError:", e)
try:
    print((2 ** 70) >> -(2 ** 70))
except ValueError as e:
    print("ValueError:", e)
