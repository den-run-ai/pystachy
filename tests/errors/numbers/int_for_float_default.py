# error: expected float, got int (write a float literal like 1.0, or use float())
# An int argument compiles a function for it (#711), and float storage holds an int (#1534),
# but a float parameter's default is a float
def scale(v: float, k: float = 2) -> float:
    return v * k


print(scale(1.5))
