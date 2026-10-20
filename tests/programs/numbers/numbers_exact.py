xs = [0.1] * 10
print(sum(xs), sum([1e100, 1.0, -1e100]), sum([0.1] * 10, 0), sum([1, 2], 10), sum([0.5], 1.5), sum(x * 0.1 for x in range(10)))
n = 9007199254740993
x = 9007199254740992.0
print(n == x, n > x, n != x, 9223372036854775807 < 9.223372036854775807e18, x < n, float("nan") == 1, 1 != float("nan"), n >= x, x <= n)
a = 9007199254740993
print(a / 3, -a / 7, 10 / 4, 2 ** 62 / 3, 9223372036854775807 / -1, 7 / 9007199254740993)
ys = [1, 0]
print(any(10 // y > 1 for y in ys), all(y > 5 for y in ys[:0]), any(y > 5 for y in ys[:0]))


def check(v: int) -> bool:
    print("check", v)
    return v == 5


print(any(check(v) for v in [5, 0, 3]), all(check(v) for v in [1, 5]))
print(0o17, 0b101, 0x_ff, 1_000.000_1, -0x8000000000000000, 1e1_0)
z = float("inf")
w = z - z
print(f"{w:.1f}", w.hex(), f"{w}", repr(w))
print(f"{1234:08,}", f"{7: >05}", f"{'ab':05}", len(f"{'a' * 150:.120}"), f"{-42:=6}", f"{10:b}", f"{255:#x}", f"{1234567:_}", f"{123.456:.3}")
