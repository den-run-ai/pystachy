class Store[T]:
    def __init__(self, name: T, items: list[int]) -> None:
        self.__name = name
        self.__items = items
        self.__next: Store[T] | None = None

    def items(self) -> list[int]:
        return self.__items

    def link(self, other: "Store[T]") -> None:
        self.__next = other

    def next_name(self) -> T:
        assert self.__next is not None
        return self.__next.__name

    def name(self) -> T:
        return self.__name
