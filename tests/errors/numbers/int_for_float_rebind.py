# error: which passes an int for the float parameter x: pass a float, as in 1.0 or float(x), to compile it as annotated
# The function compiled for an int argument (#711) binds its parameter as a template's: an
# augmented store of a float does not retype it
def bump(x: float) -> float:
    x += 0.5
    return x


print(bump(1))
