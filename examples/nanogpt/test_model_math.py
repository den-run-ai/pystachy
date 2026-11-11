"""Small exact numerical contracts; full PyTorch/BLAS/training checks are retained."""
import math

from model import cross_entropy, gelu, layer_norm, linear
from ndarray import array, array2, matmul, zeros
import pytest


def test_linear_uses_output_input_weight_layout():
    value = linear(array2([[1.0, 2.0]]), array2([[3.0, 4.0], [5.0, 6.0]]), array([1.0, -1.0]), matmul)
    assert value.shape == [1, 2]
    assert value.values() == [12.0, 16.0]


def test_constant_layer_norm_and_zero_gelu():
    result = layer_norm(array2([[2.0, 2.0]]), array([3.0, 4.0]), array([1.0, -1.0]))
    assert result.values() == [1.0, -1.0]
    assert gelu(zeros([2, 3])).values() == [0.0] * 6


def test_uniform_cross_entropy_and_ignored_targets():
    logits = zeros([1, 2, 2])
    actual = cross_entropy(logits, [0, 1])
    assert math.isfinite(actual)
    assert abs(actual - math.log(2.0)) < 1e-15
    assert math.isnan(cross_entropy(logits, [-1, -1]))


@pytest.mark.parametrize("targets", [[0], [0, 2], [-2, 1]])
def test_invalid_targets_reject(targets: list[int]):
    with pytest.raises(ValueError):
        cross_entropy(zeros([1, 2, 2]), targets)
