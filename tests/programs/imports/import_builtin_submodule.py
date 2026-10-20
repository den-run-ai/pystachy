# import pkg.sub binds pkg to the package, also where sub is a builtin module: import collections
# and import collections.abc (in either order, at module level and in functions) bind collections
# to lib/collections, which binds abc to the builtin collections.abc as CPython's does, also in
# a function that declares collections global; os and os.path; from collections import abc
# beside another name; and a module's re-exports of collections.abc and its names (from m
# import Sequence, cabc)
import collections.abc
import collections
import os
import os.path
from collections import deque, abc
from mods.abcuse import first, is_seq, queue, Sequence, cabc
import mods.abcuse


def mapping_keys(m: collections.abc.Mapping[str, int]) -> list[str]:
    return sorted(m)


def local() -> str:
    import collections.abc
    q = collections.deque([1, 2])
    q.appendleft(0)
    return f"{list(q)} {isinstance([q], collections.abc.MutableSequence)} {isinstance(3, collections.abc.Mapping)}"


def global_import() -> bool:
    global collections
    import collections.abc
    return isinstance([1], collections.abc.Sequence) and len(collections.deque([1])) == 1


def local_alias() -> bool:
    import collections.abc as c
    return isinstance("x", c.Sequence) and not isinstance({1}, c.Sequence)


print(isinstance([1], collections.abc.Sequence), isinstance({"k": 1}, collections.abc.Sequence))
print(isinstance({"a": 1}, collections.abc.Mapping), isinstance({"a": 1}, abc.MutableMapping))
print(mapping_keys({"b": 1, "a": 2}))
print(collections.deque([3, 4], maxlen=1), deque("ab"))
print(local(), local_alias(), global_import())
print(os.path.join("a", "b"), os.sep, os.path.exists(os.devnull))
print(first([5, 6]), is_seq([1]), is_seq({1: 2}), queue(["x", "y", "z"]))
print(isinstance((1, 2), Sequence), isinstance("s", cabc.Sequence), isinstance(1, cabc.Mapping))
print(collections.__name__, mods.abcuse.collections.__name__)
