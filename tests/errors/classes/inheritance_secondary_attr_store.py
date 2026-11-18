# error: expected str, got int
# The annotation a secondary base declares types the combining class's field.
class Api:
    path: str


class Base:
    pass


class C(Base, Api):
    def __init__(self) -> None:
        self.path = 3


print(C().path)
