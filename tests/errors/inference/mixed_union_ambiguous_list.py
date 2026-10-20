# error: closed union method calls require narrowing with isinstance() first
def consume(value: list[int] | list[str]) -> None:
    if isinstance(value, list):
        # Knowing this is a list cannot establish the element storage type.
        value.append(1)


values = [1]
consume(values)
