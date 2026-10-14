# error: unsupported call hash(functools._CmpKey
# CPython raises TypeError. The subset rejects hashing user-class keys statically.
from functools import cmp_to_key


def compare(x: int, y: int) -> int:
    return x - y


print(hash(cmp_to_key(compare)(10)))
