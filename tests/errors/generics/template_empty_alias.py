# error: cannot infer the type of 'out', an empty list so far: annotate it (out: list[T] = [])
def f(*args):
    out = []
    for a in args:
        out.append(a)
    tail = out
    tail.append("end")
    return out


print(f("a"))
print(f())
