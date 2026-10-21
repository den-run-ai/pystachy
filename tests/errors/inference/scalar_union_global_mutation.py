# error: closed union arithmetic requires narrowing with isinstance() first
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
