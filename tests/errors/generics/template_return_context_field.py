# error: expected list[float | int], got list[int]
class Holder:
    def __init__(self, value: int) -> None:
        self.values = [value]


def existing(holder):
    return holder.values


result: list[int | float] = existing(Holder(1))
