# error: closed union arithmetic requires narrowing with isinstance() first

def unsafe(flag: bool) -> int:
    value: int | str = 1
    if flag:
        value = 2
    else:
        value = "changed"
    return value + 1

print(unsafe(False))
