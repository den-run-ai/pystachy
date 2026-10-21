# error: type representation exceeds 65536 bytes
# Runtime depth is only one, but the compiler must specialize every reachable static call.
def grow(x, n: int) -> int:
    if n == 0:
        return 0
    return grow((x, x), n - 1)


print(grow(1, 1))
