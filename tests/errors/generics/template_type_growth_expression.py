# error: type representation exceeds 65536 bytes
# Bound intermediate types too, before the next instance() call can check its signature.
def grow(x, n: int) -> int:
    if n == 0:
        return 0
    y = (x, x)
    z = (y, y)
    return grow(((z, z), (z, z)), n - 1)


print(grow(1, 1))
