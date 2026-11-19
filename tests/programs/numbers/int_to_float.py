# An int argument for a float parameter: the function is compiled for the int, which its body
# reads as CPython's does (#711; a rejection until then: write a float literal)
def half(x: float) -> float:
    return x / 2
print(half(3))
