# A local that holds only None so far prints as None, before a later assignment in the same
# function gives it another type: the value of a variable that only None has been given is a
# null pointer, which formats as None (this was a compile-time error before).
def f() -> None:
    x = None
    print(x)  # (y has no type yet here)
    y = "a"
    x = y
    print(x)


f()
