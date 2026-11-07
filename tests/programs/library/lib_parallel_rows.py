# Each whole row is independent; the additions within it stay left-to-right.
from struct import pack

try:
    from parallel import sum_rows_float
    from parallel import sum_rows_float as alias_rows
except ImportError:
    from parallel_reference import sum_rows_float
    from parallel_reference import sum_rows_float as alias_rows


def score(x: float) -> float:
    y = x * x + 0.5
    if x < 0.0:
        y = -y
    return y * 0.25 - x


def identity(x: float) -> float:
    return x


def main() -> None:
    # Empty, tiny, uneven row chunks, dispatch threshold and a single long row.
    for n, width in [(0, 7), (21, 7), (32767, 7), (32774, 7), (65541, 7), (65536, 65536)]:
        values = [(float(i % 19) - 9.0) * 0.125 for i in range(n)]
        expected: list[float] = []
        for row in range(n // width):
            total = 0.0
            for column in range(width):
                total = total + score(values[row * width + column])
            expected.append(total)
        for workers in [1, 2, 4, 8]:
            result = sum_rows_float(score, values, width, workers)
            assert result is not values
            assert len(result) == len(expected)
            for row in range(len(result)):
                assert pack('>d', result[row]) == pack('>d', expected[row])
        print('rows', n, width, len(expected), values == [(float(i % 19) - 9.0) * 0.125 for i in range(n)])

    # These orders distinguish strict row addition from reassociated/parallel sums.
    for row_values in [[1e16, 1.0, -1e16], [1e16, -1e16, 1.0], [-0.0, -0.0, -0.0]]:
        values = row_values * 22000
        for workers in [1, 2, 4, 8]:
            result = sum_rows_float(identity, values, 3, workers)
            total = 0.0
            for value in row_values:
                total = total + value
            assert all(pack('>d', value) == pack('>d', total) for value in result)
        print('ordered', pack('>d', total).hex())

    # Includes NaNs, infinities and signed zero, with every row compared by bits.
    special = [0.0, -0.0, float('inf'), float('-inf'), float('nan')] * 13108
    result = sum_rows_float(identity, special, 1, 4)
    for i in range(len(special)):
        assert pack('>d', result[i]) == pack('>d', 0.0 + special[i])
    print('special', [pack('>d', value).hex() for value in result[:5]])
    print('default', sum_rows_float(score, [0.0, -1.0, 2.0, 3.0], 2))
    print('alias', alias_rows(score, [0.0, -1.0, 2.0, 3.0], 2, 2))

    # Argument validation precedes allocation or callback execution.
    for width, workers in [(0, 0), (0, 1), (-1, 1), (3, 1), (2, 65)]:
        try:
            sum_rows_float(score, [1.0, 2.0], width, workers)
            assert False
        except ValueError as exc:
            print('invalid', width, workers, exc)
    empty: list[float] = []
    print('empty', sum_rows_float(score, empty, 9223372036854775807, 64))


main()
