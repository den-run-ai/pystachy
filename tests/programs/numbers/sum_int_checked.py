# sum() of a list of ints or bools from an int start adds in order with 64-bit ints: bools count
# as 0 and 1, and an empty list gives the start. Every partial sum here fits in 64 bits, also
# where the items reach both ends of the range.
seed = 5


def rnd() -> int:
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return seed


def total(xs: list[int], start: int) -> int:
    return sum(xs, start)


empty: list[int] = []
flags = [True, False, True, True]
print(sum(empty), sum(empty, -7), sum([5]), sum([5], 9223372036854775802), sum(flags), sum(flags, 10), sum([True, True], -2))
print(total([9223372036854775807, -1, -9223372036854775807], 0), total([-9223372036854775807, -1, 9223372036854775807], 1),
      total([4611686018427387904, 4611686018427387903], 0), total([-4611686018427387904, -4611686018427387904], 0))
h = 0
for i in range(2000):
    n = rnd() % 40
    xs = [(rnd() * 2147483648 + rnd()) // (1 + rnd() % 1000) * (1 if rnd() % 2 == 0 else -1) // 64 for j in range(n)]
    start = rnd() - 1073741824
    h = (h * 1000003 + total(xs, start) % 1000000007 + sum(xs) % 1000003) % 2147483647
print(h)
big = [9223372036854775807 // 4] * 4
print(sum(big), sum(big, 3), sum([x - 1 for x in big], -9223372036854775807))
