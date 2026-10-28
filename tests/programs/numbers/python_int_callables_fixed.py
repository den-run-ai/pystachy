# pystachy: python-int
# Promoting ints (docs/python-int.md) as the ints of the Callables that a module that does not opt in
# (fixed_callables) takes, keeps and calls, past 64 bits and -2**63 too, and its methods (also of a
# class hierarchy) and functions as Callables, which take and return its 64-bit ints: the Callable
# converts them, also in the tuples of its lists. Also Callables that return an object of a class
# template, and a function of 64-bit ints given for one, which a Callable[[int], int] then holds.
from typing import Callable
from fixed_callables import FNode, FixedBase, Holder, apply, apply_u, fbuild, fbuild_u, fixed_pick, fmake, make_pairs, run_pairs, third, twice

big = 2 ** 70
low = -(2 ** 63)
hold = Holder(lambda x: x * 3)
fp: Callable[[int], int] = fixed_pick(1).scale
base: FixedBase = fixed_pick(0)
tw: Callable[[int], int] = twice
print(apply_u(lambda x: x + 1, big), apply(lambda x: x + 1, 5), apply(twice, 4), hold.call(2), hold.call_u(big))
print(fp(4), base.scale(5), tw(3), tw(low // 2), fp(low // 4))
print(fbuild(lambda x: FNode(x * 2), 5).v, fbuild(fmake, 3).v, fbuild_u(lambda x: FNode(x + 1), big).v)
print(fbuild(lambda x: FNode(x), 5).v, fbuild_u(lambda x: FNode(x), big).v, fbuild(lambda x: FNode(x), low).v)
print(fbuild_u(third, 31))
th: Callable[[int], int] = third
print(th(31), th(-31), th(low))
ps: list[tuple[int, Callable[[int], int]]] = [(5, lambda x: x * big), (7, tw)]
qs = make_pairs()
print(run_pairs(ps, 3), [g(big) for g in [qs[0][1]]], [g(low // 2) + n for n, g in qs])
