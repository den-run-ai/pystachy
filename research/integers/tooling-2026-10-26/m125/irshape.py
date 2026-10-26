def low8(a: int, b: int) -> int:
    return (a + b) & 0xFF


def masked_var(a: int, m: int) -> int:
    return (a * 3) & m


print(low8(250, 10), masked_var(5, 7))
