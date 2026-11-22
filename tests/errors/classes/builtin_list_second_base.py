# error: multiple inheritance with a class that derives from a builtin container is not supported
class Stack(list[int]):
    pass


class Named:
    def __init__(self) -> None:
        self.name = "n"


class Both(Named, Stack):
    pass
