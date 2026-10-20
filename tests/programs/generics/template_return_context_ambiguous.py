# A display of an int and a float returned where a union of two list types is expected: a
# list of int | float, which is one of them.
def pair(a, b):
    return [a, b]


result: list[int | float] | list[int | float | str] = pair(1, 2.5)
print(result)
