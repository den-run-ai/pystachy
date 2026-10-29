# pystachy: dynamic-any
from typing import Any


class Bad:
    def __iter__(self) -> int:
        print('bad iter')
        return 7


bad: Any = Bad()
for action in ['iter', 'list', 'loop']:
    try:
        if action == 'iter':
            iter(bad)
        elif action == 'list':
            list(bad)
        else:
            for v in bad:
                print(v)
    except TypeError as e:
        print(action, e)


class NeedsArg:
    def __iter__(self, x: int) -> int:
        return x


arg: Any = NeedsArg()
try:
    iter(arg)
except TypeError as e:
    print('arity', e)


class Recover:
    def __init__(self) -> None:
        self.i = 0

    def __iter__(self) -> 'Recover':
        print('recover iter')
        return self

    def __next__(self) -> int:
        self.i += 1
        if self.i == 1 or self.i == 3:
            raise StopIteration('pause')
        if self.i == 5:
            raise ValueError('next failure')
        return self.i


def fallback() -> str:
    print('default evaluated')
    return 'default'


r: Any = Recover()
print(iter(r) is r)
print(next(r, fallback()))
print(next(r, fallback()))
try:
    next(r)
except StopIteration as e:
    print('stop details', e)
print(next(r, None))
try:
    next(r, fallback())
except ValueError as e:
    print(e)
print(next(r))


class Early:
    def __init__(self) -> None:
        self.i = 0

    def __iter__(self) -> 'Early':
        return self

    def __next__(self) -> int:
        self.i += 1
        if self.i > 1:
            raise ValueError('overconsumed')
        return 1


e: Any = Early()
print('lazy any', any(e), e.i)
e = Early()
print('lazy contains', 1 in e, e.i)


class Reverse:
    def __reversed__(self):
        print('reversed called')
        yield 9
        yield 7

    def __iter__(self):
        raise ValueError('wrong protocol')
        yield 0


rev: Any = Reverse()
print(list(reversed(rev)))
for bad in [1, None]:
    try:
        reversed(bad)
    except TypeError as e:
        print(e)
