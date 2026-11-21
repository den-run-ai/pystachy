# A call may change the enclosing variable: the read after it is the union's, whose str has no
# + with an int.
def unsafe() -> int:
    value: int | str = 1
    def change() -> None:
        nonlocal value
        value = "changed"
    if isinstance(value, int):
        change()
        return value + 1
    return 0

print(unsafe())
