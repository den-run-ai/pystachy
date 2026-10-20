# sum(), math.fsum() and math.dist() of lists of int | float items, as CPython takes them: sum()
# adds ints exactly until the first float, then floats with its compensated sum (an int after
# that as a float, not compensated); fsum() and dist() make a float of each item.
import math

xs: list[int | float] = [1, 2.5, 3]
print(sum(xs), sum(xs, 10), sum(xs, 0.5))
ints: list[int | float] = [1, 2, 3]
print(repr(sum(ints)), repr(sum(ints, 0.0)), repr(math.fsum(ints)))
tiny: list[int | float] = [1e16, 1, -1e16, 0.1, 0.1, 0.1]
print(sum(tiny), math.fsum(tiny))
flo: list[int | float] = [0.1] * 10 + [1]
print(sum(flo), math.fsum(flo))
edge: list[int | float] = [1, 2.5, 2**53 + 1]
mid: list[int | float] = [0.1, 1, 0.2]
negz: list[int | float] = [-0.0]
print(sum(edge), sum(mid), repr(sum(negz)), repr(sum(negz, -0.0)))
inf = float("inf")
withinf: list[int | float] = [1, inf, 2.5]
infs: list[int | float] = [inf, -inf, 1]
print(sum(withinf), sum(infs))
empty: list[int | float] = []
print(repr(sum(empty)), repr(sum(empty, 0.0)))
bools: list[bool | int] = [True, 2, False]
print(sum(bools))
print(sum(x for x in xs), sum((x * 2 for x in xs), 1), sum(x for x in tiny))
p: list[int | float] = [0, 3]
q: list[int | float] = [4.0, 0]
print(math.dist(p, q))
