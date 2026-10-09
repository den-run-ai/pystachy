# error: 'Plain' object doesn't support item deletion
class Plain:
    def __getitem__(self, i: int) -> int:
        return i


del Plain()[0]
