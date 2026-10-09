# error: cannot infer the type of 'x' from None here, before a value of another type is assigned to it; annotate it (x: T | None)
def f() -> None:
    x = None
    print(x)  # (y has no type yet here)
    y = "a"
    x = y
    print(x)


f()
