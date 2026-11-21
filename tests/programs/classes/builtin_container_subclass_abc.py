from collections.abc import Callable, Hashable, Iterable, Iterator, Mapping, MutableMapping, MutableSequence, Sequence


class Plain(list[int]):
    pass


class Hashed(list[int]):
    def __hash__(self) -> int:
        return 123


class Callback(dict[str, int]):
    def __call__(self) -> int:
        return 7


print(issubclass(Plain, Sequence), issubclass(Plain, MutableSequence), issubclass(Plain, Iterable))
print(issubclass(Plain, Hashable), isinstance(Plain(), Hashable))
print(hash(Hashed()), isinstance(Hashed(), Hashable), issubclass(Hashed, Hashable))
print(issubclass(Callback, Mapping), issubclass(Callback, MutableMapping), issubclass(Callback, Sequence))
print(isinstance(Callback(), Callable), issubclass(Callback, Callable))


class Next(list[int]):
    def __next__(self) -> int:
        return 3


print(isinstance(Next(), Iterator), issubclass(Next, Iterator))
