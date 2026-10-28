# pystachy: python-int


class PromotedNumber:
    def __init__(self, value: int) -> None:
        self.value = value

    def __int__(self) -> int:
        return self.value + 7

    def __index__(self) -> int:
        return self.value


class PromotedBadFloat:
    def __float__(self) -> int:
        return 1 << 80
