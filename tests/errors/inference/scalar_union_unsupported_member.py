# error: set[int] in a closed union is not supported

def unsupported(value: set[int] | str) -> int:
    return 0

print(unsupported("a"))
