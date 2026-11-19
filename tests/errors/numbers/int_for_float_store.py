# error: expected float, got int (write a float literal like 1.0, or use float())
# An int argument compiles a function for it (#711), but annotated storage keeps its type
def half(x: float) -> float:
    return x / 2


y: float = 3
print(half(y))
