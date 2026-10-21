# error: cannot infer what find() returns: it calls itself before a return of None shows that it returns str | None; annotate its return type
def find(xs, i):
    if i >= len(xs):
        return "end"
    rest = find(xs, i + 1)
    if rest == "x":
        return None
    return xs[i]


print(find(["a", "x"], 0))
