# pystachy: dynamic-any
from typing import Any
class Numbers:
    def __iter__(self):
        print('one')
        yield 3
        print('two')
        yield 2
        print('three')
        yield 1

def key(x: Any) -> Any:
    print('key', x)
    return x
n: Any = Numbers()
print(min(n, key=key))
