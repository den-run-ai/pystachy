# round(x, n) of an int for every n that changes it: the nearest multiple of 10**-n, ties to the
# even multiple, with a quotient that rounds toward the smaller number for a negative x. 10**19
# is past 64 bits: every int that rounds to a 64-bit int there rounds to 0, as from 10**20 on.
seed = 7


def rnd() -> int:
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return seed


def num() -> int:
    # below 9 * 10**18 in magnitude, so that its rounding to a multiple of 10**18 is a 64-bit int
    v = (rnd() * 2147483648 + rnd()) * 2 + rnd() % 2
    v = v % (1 << (1 + rnd() % 62)) if rnd() % 3 == 0 else v % 9000000000000000000
    return v if rnd() % 2 == 0 else -v


h = 0
for i in range(40000):
    x = num()
    n = -(rnd() % 18) - 1
    r = round(x, n)
    h = (h * 1000003 + r % 1000000007) % 2147483647
print(h)
for n in range(-22, 2):
    m = 10 ** -n if -19 < n < 0 else 1
    t = m // 10
    xs = [0, 1, -1, 5 * t, -5 * t, 15 * t, -15 * t, 25 * t, -25 * t, 5 * t + 1, -5 * t - 1, 5 * t - 1, 1 - 5 * t,
          149 * (t // 10), -151 * (t // 10), 4999999999999999999, -4999999999999999999, 5000000000000000000, -5000000000000000000,
          123456789012345678, -987654321098765432]
    print(n, [round(x, n) for x in xs if n > -19 or -5000000000000000000 <= x <= 5000000000000000000])
print(round(9223372036854775807, 0), round(-9223372036854775807 - 1, 3), round(-9223372036854775807 - 1, -17), round(8500000000000000000, -18),
      round(-8500000000000000000, -18), round(7500000000000000000, -18), round(9223372036854775807, -30), round(-9223372036854775807 - 1, -20))
