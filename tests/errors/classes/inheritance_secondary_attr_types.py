# error: attribute 'path' that secondary base Other declares as int is str in 'C' (not supported)
class Api:
    path: str


class Other:
    path: int


class Base:
    pass


class C(Base, Api, Other):
    pass
