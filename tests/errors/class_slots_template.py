# error: field 'extra' is outside __slots__ of 'Box'
class Box:
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value
        self.extra = value


print(Box(1).value)
