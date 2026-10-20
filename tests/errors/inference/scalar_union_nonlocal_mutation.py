# error: closed union arithmetic requires narrowing with isinstance() first

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
