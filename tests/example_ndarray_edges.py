# NumPy 2.3.5 references; check_numpy.py also compares these cases with installed NumPy.
from ndarray import NDArray, array2, sum_axis, zeros


# Reversing the slow axis must not turn it into a pairwise reduction. These values
# produce 0.0 in sequential order and 84.0 with pairwise summation.
a = array2([[v, v] for v in [1e16] + [1.0] * 100 + [-1e16]])
for rstep in [1, -1]:
    for cstep in [1, -1]:
        offset = (202 if rstep < 0 else 0) + (1 if cstep < 0 else 0)
        view = NDArray(a.data, [102, 2], [2 * rstep, cstep], offset)
        assert sum_axis(view, 0).values() == [0.0, 0.0]
        assert sum_axis(view.T, 1).values() == [0.0, 0.0]
print("reversed slow axes preserve summation order")

# A singleton axis has no traversal, so its stride does not decide reduction order.
for step in [1, -1]:
    view = NDArray(a.data, [102, 1], [2 * step, -1], 202 if step < 0 else 0)
    assert sum_axis(view, 0).values() == [84.0]
    assert sum_axis(view.T, 1).values() == [84.0]
print("strided singleton axes preserve pairwise summation")

for shape in [[0, 4611686018427387904], [-1, 4611686018427387904], [0, 4294967296, 4294967296]]:
    try:
        zeros([0]).reshape(shape)
    except ValueError as e:
        assert str(e) == "array is too big; `arr.size * arr.dtype.itemsize` is larger than the maximum possible size."
    else:
        raise AssertionError("reshape accepted unrepresentable byte extents")
assert zeros([0]).reshape([0, 1024]).shape == [0, 1024]
assert zeros([0]).reshape([-1, 1024]).shape == [0, 1024]
print("empty reshape checks byte extents after inference")
