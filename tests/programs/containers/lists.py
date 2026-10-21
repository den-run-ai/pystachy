xs = [5, 3, 8, 1]
xs.append(7)
xs.insert(0, 9)
xs.insert(-1, 4)
xs.insert(100, 2)
print(xs, len(xs), xs[0], xs[-1], xs[2:4], xs[:-3], xs[-2:])
print(xs.pop(), xs.pop(0), xs.pop(-2), xs)
xs.extend([10, 11])
xs.remove(8)
print(xs, xs.index(10), xs.count(3), 3 in xs, 99 in xs, 99 not in xs)
ys = sorted(xs)
xs.sort()
print(ys == xs, ys, xs is ys)
xs.reverse()
print(xs, min(xs), max(xs), sum(xs))
zs = xs.copy()
zs[0] = -1
print(xs[0], zs[0], [0] * 5, [1, 2] * 3, [1] + [2, 3], [] == xs[:0], [1, 2] < [1, 3], [2] > [1, 9])
grid: list[list[int]] = []
for r in range(3):
    row: list[int] = []
    for c in range(4):
        row.append(r * 4 + c)
    grid.append(row)
print(grid, grid[1][2], len(grid[0]))
grid[2][3] = 99
grid[0] += [100]
print(grid)
sq = [i * i for i in range(10)]
ev = [i for i in range(20) if i % 3 == 0]
st = [str(i) + "!" for i in sq if i > 10]
print(sq, ev, st)
pairs = [[i, i * i] for i in range(3)]
print(pairs)
fl = [0.5, 1.5, -2.25]
fl.sort()
print(fl, sum(fl), max(fl), [x * 2 for x in fl])
bs = [True, False, True]
print(bs, any(bs), all(bs), all([1, 2, 3]), any([0, 0]))
names = ["bob", "alice", "carol", "Dave"]
names.sort()
print(names, sorted(names)[-1], names.index("bob"))
for i, nm in enumerate(names):
    print(i, nm, end="; ")
print()
nums = list(range(5))
nums2 = list(range(10, 0, -3))
print(nums, nums2, list(range(0)), list(range(2, 5)))
nums.clear()
print(nums, len(nums), bool(nums), bool([0]))
total = 0
items = [3, 1, 4, 1, 5, 9, 2, 6]
for v in items:
    if v == 1:
        continue
    if v == 9:
        break
    total += v
print(total)
grow = [1]
for v in grow:
    if v < 5:
        grow.append(v + 1)
print(grow)
nested = [[3, 1], [1, 2], [1, 1], [2, 0]]
nested.sort()
print(nested, [1, 2] in nested, nested.index([1, 2]))
stack: list[str] = []
for tok in "1 2 + 3 *".split():
    stack.append(tok)
print(stack[1:], stack[-3:-1])
