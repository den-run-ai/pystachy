# dict(d) of a dict with a hole is a compact table: a loop that replaces each key it visits
# rebuilds it and then finds more keys than the dict had, which CPython reports
d = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}
del d[2]
e = dict(d)
for k in e:
    print(k)
    e[k + 10] = 0
    del e[k]
print(e)
