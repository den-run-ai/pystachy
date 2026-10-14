# expected: not supported by this prototype

def unsupported(value: list[int] | str) -> int:
    return 0

print(unsupported("a"))
