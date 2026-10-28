# pystachy: dynamic-any
from typing import Any


class WordIter:
    def __init__(self) -> None:
        self.i = 0

    def __iter__(self) -> 'WordIter':
        print('iterator iter')
        return self

    def __len__(self) -> int:
        print('iterator len')
        return 2

    def __next__(self) -> str:
        self.i += 1
        if self.i > 2:
            raise StopIteration
        print('next', self.i)
        return 'key' if self.i == 1 else 'value'


class Words:
    def __iter__(self) -> WordIter:
        print('source iter')
        return WordIter()

    def __len__(self) -> int:
        print('source len')
        return 5


words: Any = Words()
print('list', list(words))
print('join', ':'.join(words))
d: Any = {}
d.update([words])
print('pairs', d)


class NoLength:
    def __iter__(self):
        print('yield')
        yield 'ok'

    def __len__(self) -> int:
        print('no length')
        raise TypeError('length unavailable')


source: Any = NoLength()
print('list without length', list(source))
print('join without source length', ''.join(source))
items: Any = []
items += source
print('extend without length', items)


class Huge:
    def __iter__(self):
        print('not reached')
        yield 1

    def __len__(self) -> int:
        print('huge length')
        return 9223372036854775807


huge: Any = Huge()
try:
    list(huge)
except MemoryError:
    print('bounded length hint')

items = []
try:
    items += huge
except MemoryError:
    print('bounded extend hint', items)


class InvalidHint:
    def __iter__(self):
        yield 1

    def __len__(self):
        print('invalid length result')
        return 1.5


invalid: Any = InvalidHint()
print(list(invalid))


class IndexHint:
    def __index__(self) -> int:
        print('hint index')
        return 2


class DynamicHint:
    def __iter__(self):
        yield 'x'

    def __len__(self):
        print('dynamic length')
        return IndexHint()


dynamic_hint: Any = DynamicHint()
print(list(dynamic_hint))
