"""Optional native BLAS regression cases, run by check_blas.py in all tiers.

Every output element is compared with the existing scalar matmul (for linear(),
the scalar product plus the bias), and the checker independently compares these
same operands/results with NumPy.
"""

import math

from ndarray import NDArray, array2, matmul as scalar_matmul, zeros
from ndarray_blas import linear, matmul


def matrix(rows: int, columns: int, seed: int) -> NDArray:
    return array2([[float((i * columns + j + seed) * 17 % 31 - 15) / 13.0
                    for j in range(columns)] for i in range(rows)])


def cases() -> list[tuple[str, NDArray, NDArray]]:
    backing = [float(i - 20) / 7.0 for i in range(80)]
    a = matrix(3, 4, 1)
    square = matrix(3, 3, 2)
    shared = matrix(2, 3, 3)
    return [
        ("contiguous", a, matrix(4, 5, 2)),
        ("prefix", NDArray(backing, [2, 3], [3, 1], 0), matrix(3, 2, 4)),
        ("left_transpose", a.T, matrix(3, 2, 5)),
        ("right_transpose", a, matrix(5, 4, 6).T),
        ("both_transposed", matrix(4, 3, 7).T, matrix(5, 4, 8).T),
        ("offset_contiguous", NDArray(backing, [2, 3], [3, 1], 5), matrix(3, 2, 9)),
        ("strided", NDArray(backing, [3, 4], [13, 2], 1), matrix(4, 2, 10)),
        ("padded_rows", NDArray(backing, [3, 4], [7, 1], 0), matrix(4, 2, 10)),
        ("padded_transpose", NDArray(backing, [3, 4], [1, 6], 0), matrix(4, 2, 10)),
        ("right_padded_rows", a, NDArray(backing, [4, 2], [5, 1], 0)),
        ("right_padded_transpose", a, NDArray(backing, [4, 2], [1, 7], 0)),
        ("reverse_rows", NDArray(a.data, [3, 4], [-4, 1], 8), matrix(4, 2, 11)),
        ("reverse_columns", NDArray(a.data, [3, 4], [4, -1], 3), matrix(4, 2, 12)),
        ("reverse_both", NDArray(a.data, [3, 4], [-4, -1], 11), matrix(4, 2, 13)),
        ("mixed_strides", NDArray(backing, [3, 4], [-13, 2], 30), matrix(4, 2, 14)),
        ("broadcast_rows", NDArray(a.data, [3, 4], [0, 1], 0), matrix(4, 2, 15)),
        ("broadcast_columns", NDArray(a.data, [3, 4], [1, 0], 0), matrix(4, 2, 16)),
        ("singleton_strides", NDArray(backing, [1, 3], [-9223372036854775807 - 1, 1], 0),
         NDArray(backing, [3, 1], [1, 9223372036854775807], 2)),
        ("shared_views", shared, NDArray(shared.data, [3, 2], [2, 1], 0)),
        ("same_operand", square, square),
        ("empty_rows", zeros([0, 3]), zeros([3, 2])),
        ("empty_columns", zeros([2, 3]), zeros([3, 0])),
        ("empty_inner", zeros([2, 0]), zeros([0, 4])),
        ("empty_all", zeros([0, 0]), zeros([0, 0])),
    ]


def linear_cases() -> list[tuple[str, NDArray, NDArray, NDArray, bool]]:
    # (label, x, weight, bias, whether the bias is passed): x @ weight.T + bias
    backing = [float(i - 20) / 7.0 for i in range(80)]
    x = matrix(3, 4, 21)
    weight = matrix(5, 4, 22)
    bias = NDArray([float(j) / 8.0 - 0.25 for j in range(5)], [5], [1], 0)
    return [
        ("contiguous", x, weight, bias, True),
        ("no_bias", x, weight, bias, False),
        ("padded_input", NDArray(backing, [3, 4], [7, 1], 0), weight, bias, True),
        ("offset_input", NDArray(backing, [3, 4], [4, 1], 9), weight, bias, True),
        ("transposed_input", matrix(4, 3, 23).T, weight, bias, True),
        ("transposed_weight", x, matrix(4, 5, 24).T, bias, True),
        ("strided_bias", x, weight, NDArray(backing, [5], [3], 2), True),
        ("shared_input_weight", NDArray(backing, [3, 4], [4, 1], 0), NDArray(backing, [5, 4], [4, 1], 0), bias, True),
        ("bias_shares_weight", x, weight, NDArray(weight.data, [5], [4], 0), True),
        ("empty_rows", zeros([0, 4]), weight, bias, True),
        ("empty_features", x, zeros([0, 4]), zeros([0]), True),
        ("empty_inner", zeros([3, 0]), zeros([5, 0]), bias, True),
    ]


def scalar_linear(x: NDArray, weight: NDArray, bias: NDArray, use_bias: bool) -> NDArray:
    result = scalar_matmul(x, weight.T)
    if use_bias:
        result += bias
    return result


def same_values(actual: list[float], expected: list[float]) -> None:
    assert len(actual) == len(expected)
    for i in range(len(actual)):
        x = actual[i]
        y = expected[i]
        assert math.isfinite(x) and math.isfinite(y)
        assert abs(x - y) <= 1e-12 * max(1.0, abs(x), abs(y))


def rejection(label: str, a: NDArray, b: NDArray) -> None:
    try:
        matmul(a, b)
    except (ValueError, OverflowError) as error:
        print("ERROR", (label, str(error)))
        return
    raise AssertionError("invalid BLAS input accepted: " + label)


def linear_rejection(label: str, x: NDArray, weight: NDArray, bias: NDArray) -> None:
    try:
        linear(x, weight, bias)
    except (ValueError, OverflowError) as error:
        print("ERROR", (label, str(error)))
        return
    raise AssertionError("invalid BLAS linear input accepted: " + label)


def check_linear() -> None:
    for label, x, weight, bias, use_bias in linear_cases():
        before = (list(x.data), list(weight.data), list(bias.data))
        actual = linear(x, weight, bias if use_bias else None)
        expected = scalar_linear(x, weight, bias, use_bias)
        assert actual.shape == expected.shape
        assert actual.data is not x.data and actual.data is not weight.data and actual.data is not bias.data
        assert (list(x.data), list(weight.data), list(bias.data)) == before
        same_values(actual.values(), expected.values())
        print("LINEAR", (label, actual.shape, actual.values()))
        # The bias is read afresh on every call, as training updates it in place.
        if use_bias and bias.size != 0 and actual.size != 0:
            original = bias.data[bias.offset]
            bias.data[bias.offset] += 0.5
            same_values(linear(x, weight, bias).values(), scalar_linear(x, weight, bias, True).values())
            bias.data[bias.offset] = original

    x = matrix(3, 4, 25)
    weight = matrix(5, 4, 26)
    linear_rejection("linear_bias_length", x, weight, zeros([4]))
    linear_rejection("linear_bias_rank", x, weight, zeros([1, 5]))
    linear_rejection("linear_inner_mismatch", x, matrix(5, 3, 27), zeros([5]))
    linear_rejection("linear_input_rank", NDArray([1.0, 2.0, 3.0, 4.0], [4], [1], 0), weight, zeros([5]))
    # The output's extent is checked before the bias is expanded into it.
    huge = NDArray([], [2147483647, 0], [0, 1], 0)
    linear_rejection("linear_output_byte_extent", huge, huge, NDArray([0.0], [2147483647], [0], 0))


def main() -> None:
    for label, a, b in cases():
        left_before = list(a.data)
        right_before = list(b.data)
        actual = matmul(a, b)
        expected = scalar_matmul(a, b)
        assert actual.shape == expected.shape
        assert actual.data is not a.data and actual.data is not b.data
        assert a.data == left_before and b.data == right_before
        # Repeated calls must see new input values (especially weight.T); the
        # adapter has no cached packed copy that could hide training updates.
        if a.size != 0 and b.size != 0:
            original = a.data[a.offset]
            a.data[a.offset] += 0.25
            same_values(matmul(a, b).values(), scalar_matmul(a, b).values())
            a.data[a.offset] = original
        same_values(actual.values(), expected.values())
        print("CASE", (label, actual.shape, actual.values()))
        # Mutating the result must leave both operands unchanged, even if A/B
        # share their backing list, or the input is a view into a larger array.
        if actual.size != 0:
            actual.data[0] += 123.0
            assert a.data == left_before and b.data == right_before

    one = array2([[1.0]])
    data = [1.0, 2.0, 3.0, 4.0]
    rejection("rank", NDArray(data, [4], [1], 0), one)
    rejection("stride_rank", NDArray(data, [1, 1], [1], 0), one)
    rejection("negative_dimension", NDArray(data, [-1, 1], [1, 1], 0), one)
    rejection("lp64_dimension", NDArray([], [2147483648, 0], [0, 1], 0), zeros([0, 1]))
    rejection("input_byte_extent", NDArray([1.0], [2147483647, 2147483647], [0, 0], 0), one)
    rejection("output_byte_extent", zeros([2147483647, 0]), zeros([0, 2147483647]))
    rejection("negative_offset", NDArray(data, [1, 1], [1, 1], -1), one)
    rejection("past_end_offset", NDArray(data, [1, 1], [1, 1], 4), one)
    rejection("empty_offset", NDArray(data, [0, 1], [1, 1], 5), one)
    rejection("positive_extent", NDArray(data, [2, 2], [3, 1], 0), one)
    rejection("negative_extent", NDArray(data, [2, 2], [-3, 1], 2), one)
    rejection("positive_overflow", NDArray(data, [2, 2], [9223372036854775807, 1], 0), one)
    rejection("negative_overflow", NDArray(data, [2, 2], [-9223372036854775807 - 1, 1], 3), one)
    rejection("inner_mismatch", zeros([2, 3]), zeros([4, 2]))
    rejection("empty_inner_mismatch", zeros([0, 3]), zeros([4, 0]))
    check_linear()


if __name__ == "__main__":
    main()
