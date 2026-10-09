# error: Problem.__init__() takes 2 positional arguments but 3 were given
class Problem(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)


raise Problem("a", "b")
