# expected: expected int, got str

def unsupported(flag: bool) -> int:
    value = 1
    if flag:
        value = "a"
    return value

print(unsupported(True))
