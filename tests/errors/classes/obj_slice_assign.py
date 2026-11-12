# error: expected int, got slice
class C:
    def __setitem__(self, k: int, v: int) -> None:
        pass


C()[1:2] = [3]
