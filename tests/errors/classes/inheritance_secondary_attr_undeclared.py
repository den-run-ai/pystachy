# error: secondary base methods may not use super() or read or write the instance
# A secondary base's methods read and store the attributes it declares, not others.
class Api:
    path: str

    def show(self) -> str:
        return self.path + self.suffix


class Base:
    pass


class C(Base, Api):
    def __init__(self) -> None:
        self.path = "p"
        self.suffix = "!"
