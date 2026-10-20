# error: expected int, got str (perhaps because 'out' of pair() is always empty for these arguments, and taken as list[int]: annotate it (out: list[T] = []))
def pair(*args):
    out = []
    for a in args:
        out.append(a)
    return out, len(args)


xs, n = pair()
xs.append("s")
print(xs, n)
