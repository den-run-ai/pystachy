# list core: growth, inline and array storage, pops, inserts, slices, steps, reverse, clear, extend
def show(xs: list[int]) -> None:
    print(len(xs), xs)


def strs() -> None:
    ws: list[str] = []
    for i in range(7):
        ws.append("w" + str(i))
        print(len(ws), ws[-1], ws[0])
    ws.insert(0, "first")
    ws.insert(-1, "pen")
    ws.insert(100, "last")
    ws.insert(-100, "zeroth")
    print(ws)
    print(ws.pop(), ws.pop(0), ws.pop(-2), ws)
    del ws[1]
    del ws[-1]
    print(ws, ws[::-1], ws[1:3], ws[::2], ws[5:1:-2], ws[:], ws[10:], ws[-2:])
    ws.reverse()
    print(ws)
    c = ws.copy()
    c.extend(ws)
    c.extend(c)
    print(len(c), c[:3], c[-3:])
    ws.clear()
    print(ws, len(ws))
    ws.append("again")
    print(ws)
    while len(c) > 0:
        c.pop()
    c.append("refill")
    c.append("more")
    print(c)


xs: list[int] = []
show(xs)
for i in range(20):
    xs.append(i * i)
show(xs)
xs[3] = -3
xs[-1] = -1
print(xs[0], xs[19], xs[-20], xs[7])
print(xs.pop(), xs.pop(0), xs.pop(5), xs.pop(-3))
show(xs)
xs.insert(2, 222)
xs.insert(0, 111)
xs.insert(len(xs), 999)
xs.insert(-1, 888)
show(xs)
del xs[0]
del xs[-2]
show(xs)
print(xs[2:5], xs[:3], xs[-3:], xs[5:2], xs[::3], xs[::-1], xs[10:2:-3], xs[-1:-8:-2], xs[100:], xs[:-100])
ys = xs.copy()
ys.reverse()
show(ys)
ys.extend(xs)
ys.extend(ys)
show(ys)
ys.clear()
show(ys)
ys.append(5)
ys.extend([1, 2, 3])
show(ys)
fs = [1.5, 2.5]
for i in range(10):
    fs.append(float(i) / 4)
fs.reverse()
print(fs, fs[1:4], fs[::4])
strs()
for bad in range(5):
    try:
        if bad == 0:
            print(xs[100])
        elif bad == 1:
            xs[-100] = 1
        elif bad == 2:
            del xs[len(xs)]
        elif bad == 3:
            print(ys.pop(10))
        else:
            e: list[int] = []
            e.pop()
    except IndexError as err:
        print("IndexError:", err)
try:
    print(xs[::0])
except ValueError as err:
    print("ValueError:", err)
big = list(range(1000))
t = 0
while len(big) > 0:
    t += big.pop() + (big.pop(0) if len(big) > 0 else 0)
print(t)
nested = [[i, i + 1] for i in range(5)]
nested.insert(2, [9])
nested[0].extend(nested[1])
print(nested, nested[::2], nested[1:][0])
