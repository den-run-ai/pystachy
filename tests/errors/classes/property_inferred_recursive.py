# error: cannot infer what down() returns: it calls itself before a return statement does; annotate its return type
class C:
    def __init__(self, n: int) -> None:
        self.n = n

    @property
    def down(self):
        if self.n > 0:
            return C(self.n - 1).down
        return 0


print(C(3).down)
