# A template's fresh display of an int and a float: a list of their union, with or
# without an expected type.
def pair(a, b):
    return [a, b]


contextual: list[int | float] = pair(1, 2.5)
print(pair(1, 2.5))
