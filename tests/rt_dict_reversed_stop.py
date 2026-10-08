# reversed(dict) as CPython 3.13.16 steps it: a rebuild that leaves the loop's position past the
# entries ends the loop, instead of walking down from the last entry and meeting keys again
d = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}
del d[0]
del d[1]
del d[2]
n = 0
for k in reversed(d):
    n += 1
    print("got", k, len(d))
    if n == 1:
        d[100] = 1
        del d[3]
print("end", d)

e = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}
del e[0]
del e[1]
del e[2]
for k in reversed(e):
    print(k)
    e[100 + k] = 0
    del e[100 + k]
print(e)

s = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}
del s["a"]
del s["b"]
del s["c"]
for w in reversed(s):
    print(w)
    s[w + w] = 0
    del s[w + w]
print(s)

# without a rebuild, holes are skipped and every key comes once
f = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
del f[1]
del f[4]
for k in reversed(f):
    print(k, end=" ")
    if k == 3:
        f[9] = 9
        del f[9]
print(f)
