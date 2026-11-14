# error: attribute 'path' that secondary base Api declares is a method or property of 'C' (not supported)
class Api:
    path: str


class Base:
    pass


class C(Base, Api):
    def path(self) -> str:
        return "p"
