# error: MutableMapping.pop() got an unexpected keyword argument 'default'
# MutableMapping.pop's default is positional only here (pop(key, *default), which tells whether a
# default is given): CPython's takes default= too
from collections.abc import MutableMapping


class Store(MutableMapping):
    def __init__(self) -> None:
        self.d: dict[str, int] = {}

    def __getitem__(self, k: str) -> int:
        return self.d[k]

    def __setitem__(self, k: str, v: int) -> None:
        self.d[k] = v

    def __delitem__(self, k: str) -> None:
        del self.d[k]

    def __iter__(self):
        return iter(self.d)

    def __len__(self) -> int:
        return len(self.d)


print(Store().pop("a", default=0))
