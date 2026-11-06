xs = ["a"]
t: tuple[str, ...] = ("b", "c")
xs.extend(t)
print(xs)
