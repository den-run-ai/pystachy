# error: expected float, got int (write a float literal like 1.0, or use float()) (compiling add(list[float], int)
# The int that a function compiled for it (#711) stores into a list[float], which holds floats
def add(xs: list[float], x: float) -> None:
    xs.append(x)


xs = [1.5]
add(xs, 2)
print(xs)
