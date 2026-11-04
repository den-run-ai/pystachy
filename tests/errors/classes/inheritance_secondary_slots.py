# error: __slots__ in a hierarchy with a secondary base is not supported
class Storage:
    __slots__ = ("value",)

    def __init__(self, value: int) -> None:
        self.value = value


class Reader:
    def read(self) -> int:
        return 1


class Both(Storage, Reader):
    pass
