# Generators with bytes (#490 with #493): bytes() of a generator's ints, generators of bytes
# slices, b"".join() and max() of them, a generator expression over bytes.
from collections.abc import Iterator


def nums(n: int) -> Iterator[int]:
    for i in range(n):
        yield 65 + i


def chunks(data: bytes, k: int) -> Iterator[bytes]:
    for i in range(0, len(data), k):
        yield data[i:i + k]


print(bytes(nums(3)), bytes(x + 1 for x in nums(2)))
print(list(chunks(b"abcdefg", 3)), b"-".join(chunks(b"abcdef", 2)))
for c in chunks(b"xyz", 1):
    print(c)
g = (b for b in b"hi")
print(list(g))
print(sum(b"abc"), max(chunks(b"abcd", 2)))
