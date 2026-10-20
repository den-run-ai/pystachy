# error: argument of type 'Plain' is not iterable
class Plain:
    def __init__(self) -> None:
        self.xs = [1]


print(1 in Plain())
