def make(value: float | None) -> list[float | None]:
    return [value, None, value]


def replace(values: list[float | None], value: float | None) -> float | None:
    old = values[0]
    values[0] = value
    return old


def frozen(values: list[float | None]) -> tuple[float | None, ...]:
    return tuple(values)


def first(values: tuple[float | None, ...]) -> float | None:
    return values[0]
