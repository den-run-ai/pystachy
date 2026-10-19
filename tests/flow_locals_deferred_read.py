# A local that a lambda reads, given an int after a str: int | str, which the lambda reads
# after the rebinding.
def f() -> int:
    value = "3"
    read = lambda: value
    value = int(value)
    print(repr(read()))
    return value
print(f())
