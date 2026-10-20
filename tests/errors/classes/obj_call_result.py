# error: 'P' object is not callable
class P:
    def __init__(self) -> None:
        self.n = 1


print([P()][0](1))
