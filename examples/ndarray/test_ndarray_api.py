"""Exact small array/view checks; NumPy and BLAS integration remain independent."""
from ndarray import array, array2, matmul, sum_axis, total, zeros
import pytest


def test_transpose_and_reshape_share_storage_but_copy_does_not():
    source = array2([[1.0, 2.0], [3.0, 4.0]])
    transposed = source.T
    flattened = source.reshape([4])
    copied = source.copy()
    transposed[0, 1] = 9.0
    assert source.values() == [1.0, 2.0, 9.0, 4.0]
    assert flattened.values() == source.values()
    assert copied.values() == [1.0, 2.0, 3.0, 4.0]


def test_broadcast_reduction_and_matrix_product():
    left = array2([[1.0, 2.0], [3.0, 4.0]])
    right = array2([[5.0, 6.0], [7.0, 8.0]])
    assert matmul(left, right).values() == [19.0, 22.0, 43.0, 50.0]
    assert (left + array([10.0, 20.0])).values() == [11.0, 22.0, 13.0, 24.0]
    assert sum_axis(left, 0).values() == [4.0, 6.0]
    assert sum_axis(left, 1).values() == [3.0, 7.0]
    assert total(left) == 10.0


@pytest.mark.parametrize("shape", [[3], [1, 3], [-1, -1]])
def test_invalid_reshape(shape: list[int]):
    with pytest.raises(ValueError):
        zeros([2, 2]).reshape(shape)


def test_negative_dimensions_and_ragged_rows_reject():
    with pytest.raises(ValueError):
        zeros([-1])
    with pytest.raises(ValueError):
        array2([[1.0], [2.0, 3.0]])
