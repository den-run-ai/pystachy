# Runtime-length tuples take scalar projections, not enumerate/zip's tuple-valued items.
print(tuple(value for index, value in enumerate("ab")))
print(tuple(left + right for left, right in zip([1, 2], [3, 4])))
