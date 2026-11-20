# A call may change the global: the read after it is the union's, whose str has no + with an int.
value: int | str = 1

def change() -> None:
    global value
    value = "changed"

def unsafe() -> int:
    if isinstance(value, int):
        change()
        return value + 1
    return 0

print(unsafe())
