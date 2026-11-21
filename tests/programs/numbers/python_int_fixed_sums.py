# pystachy: python-int
# A module that does not opt in adds a list of this module's ints with 64-bit arithmetic. The list
# may hold an int past 64 bits at other times: here it holds none while that module reads it, also
# after one was appended and removed, and where an item is the smallest 64-bit int.
from fixed_sums import count, product, total

xs = [1, 2, 3, 2 ** 62]
empty: list[int] = []
print(total(xs, 5), product([3, 5, 7]), total(empty, 9), count([True, False, True]))
xs.append(2 ** 70)
print(sum(xs), xs[-1] - 2 ** 70)
xs.pop()
print(total(xs, -(2 ** 62)), sum(xs) + 2 ** 64, product(xs[:3]))
ys = [2 ** 63 - 1, -(2 ** 63), 1]
print(total(ys, 0), total([y // 2 for y in ys], 0), sum(ys, 2 ** 63))
zs = [2 ** 64, 5]
zs[0] = -(2 ** 63)
print(total(zs, 2 ** 63 - 5), total(zs[1:], 0))
