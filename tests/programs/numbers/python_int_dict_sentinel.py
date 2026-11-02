# pystachy: python-int
# A dict of int keys holds -2**63 in the slot of a key past 64 bits, and -2**63 is a 64-bit key too:
# neither key's lookups find the other, also where CPython's hash of both is the same (-4). This is
# python_int_any_dict_eq's collision in a native table, through the int probe (subscripts, get,
# setdefault, pop, in, del) and the generic one (==, update() of a dict that has keys, fromkeys()).
small = -2 ** 63
collision = -16 * (2 ** 61 - 1) - 4
print(hash(small), hash(collision))
colliding: dict[int, int] = {collision: 1, small: 2, 0: 3}
print(len(colliding), colliding[collision], colliding[small], colliding[0])
print(colliding.get(collision), colliding.get(small), colliding.setdefault(small, 8))
copy = dict(colliding)
print(colliding == copy, colliding == {small: 2, 0: 3, collision: 1}, colliding == {small: 2, 0: 3, collision + 1: 1})
merged: dict[int, int] = {small: 0, 5: 5}
merged.update(colliding)
print(merged, dict.fromkeys(colliding, 7))
print(colliding.pop(small), len(colliding), collision in colliding, small in colliding)
colliding[small] = 5
print(colliding.pop(collision), colliding[small], len(colliding))
del colliding[small]
print(colliding, small in colliding, collision in colliding)
