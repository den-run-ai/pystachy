# Module globals first None, given values in a loop below, where the value's type is
# known only once the loop's variable is.
best = None
for v in [3, 1, 2]:
    if best is None or v < best:
        best = v
print(best)
last = None
for w in ["a", "b"]:
    last = w
print(last)
