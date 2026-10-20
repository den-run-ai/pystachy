# reversed(dict): a rebuild compacts the entries below the loop's position, so CPython 3.13.16
# meets key 4 a second time, and fails once the loop has produced len(d) items
d = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}
del d[0]
del d[1]
for k in reversed(d):
    print(k)
    d[100 + k] = 0
    del d[100 + k]
print(d)
