# concatenation of variable-length tuples (tomllib's Key = tuple[str, ...])
from typing import Tuple

Key = Tuple[str, ...]


def join(header: Key, key: Key) -> Key:
    parent = key[:-1]
    return header + parent


print(join(("a", "b"), ("c", "d", "e")))
