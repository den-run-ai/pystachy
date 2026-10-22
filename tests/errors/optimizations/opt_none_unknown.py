# error: NoneType | None values cannot be compared or printed
def f() -> None:
    x = None
    print(x)  # (y has no type yet here)
    y = "a"
    x = y
    print(x)


f()
