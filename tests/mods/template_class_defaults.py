def initial() -> str:
    print("default")
    return "initial"


class Base:
    count = 0

    def __init__(self, x):
        self.x = x

    @classmethod
    def name(cls, word: str = initial()) -> str:
        cls.count += 1
        return cls.__name__ + word
