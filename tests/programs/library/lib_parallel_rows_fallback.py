# Side effects, exceptions and future input mutations retain serial row order.
try:
    from parallel import sum_rows_float
except ImportError:
    from parallel_reference import sum_rows_float

seen: list[float] = []
values = [1.0, 2.0, 3.0, 4.0]


def record(x: float) -> float:
    seen.append(x)
    if x == 3.0:
        raise ValueError('third')
    return x


def change(x: float) -> float:
    values[3] = 9.0
    return x


def divide(x: float) -> float:
    return 1.0 / x


try:
    sum_rows_float(record, values, 2, 4)
except ValueError as exc:
    print('error', seen, exc)
print('mutation', sum_rows_float(change, values, 2, 4), values)
try:
    sum_rows_float(divide, [1.0, 2.0, 0.0, 4.0], 2, 4)
except ZeroDivisionError as exc:
    print('divide', exc)
for width, workers in [(0, 0), (0, 1), (3, 1), (2, 65)]:
    before = len(seen)
    try:
        sum_rows_float(record, [1.0, 2.0], width, workers)
    except ValueError as exc:
        print('invalid', width, workers, len(seen) == before, exc)
