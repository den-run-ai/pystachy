class Ordinary:
    def __init__(self) -> None:
        self.value = 7


class SlottedField(Ordinary):
    __slots__ = ("value",)


class Slotted:
    __slots__ = ("value",)

    def __init__(self) -> None:
        self.value = 8


class RepeatedSlot(Slotted):
    __slots__ = ("value",)


print(SlottedField().value, RepeatedSlot().value)
