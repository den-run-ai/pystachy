# error: f() returns None and an empty list whose items' type it does not show; annotate its return type (-> list[T] | None)
def f(n):
    out = []
    if n < 0:
        return None
    return out


print(f(1))
