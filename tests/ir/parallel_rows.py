from parallel import sum_rows_float


def polynomial(x: float) -> float:
    y = x * x + 0.25
    if x < 0.0:
        return -y
    return y


def scored(values: list[float], width: int, workers: int) -> list[float]:
    return sum_rows_float(polynomial, values, width, workers)


print(scored([1.0, -1.0, 0.0, 2.0], 2, 2))
