# reversed(dict): replacing each key keeps the size, but the rebuilds move entries below the
# loop's position, so it would produce more items than the dict holds: CPython 3.13.16 stops it
d = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
del d[1]
for k in reversed(d):
    del d[k]
    d[k] = 0
    print(k)
