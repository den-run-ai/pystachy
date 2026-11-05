# CPython uses ordinary ordered map; native code may dispatch only proven kernels.
import math

try:
    from parallel import map_float
    from parallel import map_float as alias_map
except ImportError:
    from parallel_reference import map_float
    from parallel_reference import map_float as alias_map


def score(x: float) -> float:
    y = x * x + 0.5
    if x < 0.0:
        y = -y
    return y * 0.25 - x


def negate(x: float) -> float:
    return -x


def rounded(x: float) -> float:
    y = x + 1e16
    return y - 1e16


def no_fma(x: float) -> float:
    return x * 1.0000000000000002 - 1.0000000000000004


def main() -> None:
    # Empty, tiny, uneven chunks and input larger than the scheduler's threshold.
    for n in [0, 1, 31, 4097, 32769, 65539]:
        values = [(float(i % 19) - 9.0) * 0.125 for i in range(n)]
        expected = [score(x) for x in values]
        for workers in [1, 2, 4, 8]:
            result = map_float(score, values, workers)
            assert result == expected
            assert result is not values
            assert len(result) == n
        print("sizes", n, values == [(float(i % 19) - 9.0) * 0.125 for i in range(n)])

    print("default", map_float(score, [0.0, -1.0, 2.0]))
    print("alias", alias_map(score, [0.0, -1.0, 2.0], 2))
    special = [0.0, -0.0, float("inf"), float("-inf"), float("nan")] * 13108
    result = map_float(negate, special, 4)
    for start in [0, 16385, 32770, 49155]:
        print("special", math.copysign(1.0, result[start]), math.copysign(1.0, result[start + 1]),
              result[start + 2], result[start + 3], math.isnan(result[start + 4]))
    many = [1.0] * 65539
    print("rounding", map_float(rounded, many, 4) == [rounded(x) for x in many])
    values = [1.0000000000000002] * 65539
    print("no-fma", map_float(no_fma, values, 4) == [0.0] * len(values))
    # These sites use a proven callback, so validation is native even when empty.
    cases: list[list[float]] = [[], [1.0]]
    for workers in [-1, 0, 65, 9223372036854775807]:
        for values in cases:
            try:
                map_float(score, values, workers)
                assert False
            except ValueError as exc:
                print("native-invalid-workers", workers, len(values), exc)
    empty: list[float] = []
    print("maximum-workers", map_float(score, empty, 64))


main()
