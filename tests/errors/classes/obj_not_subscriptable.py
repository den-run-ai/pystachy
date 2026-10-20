# error: 'Plain' object is not subscriptable
class Plain:
    def __init__(self) -> None:
        self.xs = [1]


print(Plain()[0])
