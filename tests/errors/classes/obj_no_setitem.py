# error: 'Ro' object does not support item assignment
class Ro:
    def __getitem__(self, i: int) -> int:
        return i


r = Ro()
r[0] += 1
