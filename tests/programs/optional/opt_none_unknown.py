# a local that only None has reached so far prints as None: its first read comes before the
# store that types it (y has no type yet there), which compiles the function again
def f() -> None:
    x = None
    print(x)  # (y has no type yet here)
    y = "a"
    x = y
    print(x)


f()
