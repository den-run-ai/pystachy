d = {1: 1, 2: 2, 3: 3}
for k in reversed(d):
    print(k)
    if k == 2:
        d[9] = 9
