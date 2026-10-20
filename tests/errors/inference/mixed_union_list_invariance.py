# error: expected int | list[int | str], got list[int]
def consume(value: int | list[int | str]) -> None:
    pass


values = [1, 2]
consume(values)
