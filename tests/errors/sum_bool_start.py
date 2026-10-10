# error: sum() with a bool start is not supported: it returns the bool for an empty iterable, else a number; use int(start) for a numeric result
# CPython BuiltinTest.test_sum asserts that sum([], False) is False; see upstream/CPYTHON-LICENSE.txt.
values: list[int] = []
print(sum(values, False))
