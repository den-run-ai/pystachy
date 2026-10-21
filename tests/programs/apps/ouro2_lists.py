xs = [3, 1, 4, 1, 5, 9, 2, 6]
print(len(xs), xs[0], xs[-1], xs[len(xs) - 2])
xs[0] = 30
xs[-1] = 60
xs.append(7)
print(xs[0], xs[7], xs[8], len(xs), xs.pop(), len(xs))


def total(a: list[int]) -> int:
    t = 0
    for v in a:
        t += v
    return t


def sort(a: list[int]) -> None:
    for i in range(1, len(a)):
        v = a[i]
        j = i - 1
        while j >= 0 and a[j] > v:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = v


def show(a: list[int]) -> str:
    s = "["
    for i in range(len(a)):
        if i > 0:
            s = s + ", "
        s = s + str(a[i])
    return s + "]"


sort(xs)
print(show(xs), total(xs))
e: list[int] = []
print(len(e), show(e))
for i in range(1000):
    e.append(i * i)
print(len(e), e[999], total(e))
z = [0] * 5
z[2] = 7
print(show(z), len([True] * 3))
names = ["ada", "bob"]
names.append("cy")
out = ""
for n in names:
    out = out + n + ";"
print(out, len(names), names[1][0], ord(names[2][1]))
grid: list[list[int]] = []
for r in range(3):
    row: list[int] = []
    for c in range(4):
        row.append(r * 4 + c)
    grid.append(row)
print(show(grid[2]), grid[1][3], len(grid), len(grid[0]))
flags = [True, False]
flags.append(True)
print(flags[0], flags[1], flags[2])
stack: list[int] = []
for i in range(5):
    stack.append(i)
t = 0
while len(stack) > 0:
    t = t * 10 + stack.pop()
print(t)
nested = [[1, 2], [3]]
nested[1].append(4)
print(show(nested[0]), show(nested[1]))
ys = xs
ys.append(100)
print(len(xs), xs is ys, xs is not e)
