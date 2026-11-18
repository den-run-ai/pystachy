class LoopLater:
    def __init__(self, value):
        for i in range(1):
            self.value = value
        self.value: int = self.value + 1


class LoopEarlier:
    def __init__(self, value):
        for i in range(1):
            self.value: int = value
        self.value = self.value + 1


class TryLater:
    def __init__(self, value):
        try:
            if value < 0:
                raise ValueError("negative")
            self.value = value
        except ValueError:
            self.value: int = 0


class TryEarlier:
    def __init__(self, value):
        try:
            if value < 0:
                raise ValueError("negative")
            self.value: int = value
        except ValueError:
            self.value = 0


print(LoopLater(3).value, LoopEarlier(3).value)
print(TryLater(3).value, TryLater(-1).value)
print(TryEarlier(3).value, TryEarlier(-1).value)
