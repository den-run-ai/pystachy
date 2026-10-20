# error: expected dict[str,int | str] | int, got dict[str,int]
def consume(value: int | dict[str, int | str]) -> None:
    pass


values = {"a": 1}
consume(values)
