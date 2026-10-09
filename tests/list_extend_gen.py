# list.extend() of a generator expression appends each item as it is made: the generator sees the
# items it added, and those before a raise stay.
xs = [1]
xs.extend(x + 1 for x in xs if x < 5)
print(xs)
d = {"a": 1, "b": 2}
ks: list[str] = []
try:
    ks.extend(k for k in d if d.setdefault(k + "!", 0) == 0)
except RuntimeError as e:
    print("RuntimeError", e)
print(ks)
ys = []
ys.extend(str(i) for i in range(3))
print(ys)
zs: list[int] = [0]
try:
    zs.extend(10 // (2 - i) for i in range(4))
except ZeroDivisionError:
    pass
print(zs)
ws = [3, 1, 2]
ws.extend(sorted(ws))
ws.extend([w * 2 for w in ws])
print(ws)
vs = [0]
try:
    vs.extend(int(s) for s in ["1", "x"])
except ValueError:
    pass
print(vs)
