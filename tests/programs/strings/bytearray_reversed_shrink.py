# reversed(b) reads b[i] as it reaches each i, as CPython's reversed() does: it ends where b has
# become shorter than i, and does not see bytes appended after it started.
b = bytearray(b"abcdef")
out = []
for x in reversed(b):
    out.append(x)
    if x == 102:
        del b[3:]
print(out, b)
c = bytearray(b"xyz")
seen = []
for x in reversed(c):
    seen.append(x)
    if x == 122:
        c.append(33)
print(seen, c)
