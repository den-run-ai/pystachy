# error: expected int, got str (perhaps because 'out' of f() is always empty for these arguments, and taken as list[int]: annotate it (out: list[T] = []))
def f(*args):
    out = []
    for a in args:
        out.append(a)
    if "s" in out:
        print("yes")
    return out


print(f())
