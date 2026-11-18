# error: expected bytes, got str
# (a bytes | bytearray parameter takes another argument as an annotated bytes parameter does)
def size(data: bytes | bytearray) -> int:
    return len(data)


print(size("abc"))
