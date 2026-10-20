# reversed(dict): clear() and as many new keys keep the size, but the loop then finds an entry
# after producing len(d) items, which CPython 3.13.16 reports
d = {18: 0, 27: 1, 12: 2, 20: 3, 29: 4}
del d[27]
del d[20]
n = 0
for k in reversed(d):
    n += 1
    print(k)
    if n == 2:
        d.clear()
        d[21] = 0
        d[22] = 1
        d[23] = 2
print("done", n)
