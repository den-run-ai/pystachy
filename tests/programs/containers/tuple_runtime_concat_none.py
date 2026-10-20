# A runtime-length tuple and a fixed tuple whose items are None, or of its item type or None,
# concatenate into a tuple of its item type or None, on either side, as two runtime-length
# tuples of a type and of that type or None do
nums: tuple[int, ...] = tuple([1, 2])
words: tuple[str, ...] = tuple(["a"])
print(nums + (None,), (None,) + nums, nums + (None, 3), (4, None) + nums)
print(words + (None,), (None, "b") + words, len(words + (None, None)))
maybe: int | None = None
print(nums + (maybe,), (maybe, 5) + nums, (nums + (None,))[-1] is None)
empty: tuple[int, ...] = ()
print(empty + (None,), (None,) + empty, nums + ())
