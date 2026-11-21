# A variable annotated float that is given an int holds an int | float, as if annotated so
# (#1534), and the function it is passed to compiles for that argument (#711)
def half(x: float) -> float:
    return x / 2


y: float = 3
print(half(y))
