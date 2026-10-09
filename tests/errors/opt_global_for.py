# error: cannot infer the type of 'last' from None; annotate it (last: T | None = None)
last = None
for w in ["a", "b"]:
    last = w  # (w is not typed yet where last is first assigned)
print(last)
