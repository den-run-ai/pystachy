# error: copy.copy() of a Proxy object is not supported: its class defines __getattr__, by which CPython's copy would copy it
# CPython's copy asks the new object, which no __init__ has run for, for __setstate__, and
# deepcopy asks the object for __deepcopy__: both reach its class's __getattr__ (#1536).
import copy


class Proxy:
    def __init__(self) -> None:
        self.n = 1

    def __getattr__(self, name: str) -> int:
        return 0


print(copy.copy(Proxy()).n)
