# error: 'Plain' object is not iterable
class Plain:
    def __init__(self) -> None:
        self.xs = [1]


print(sorted(Plain()))
