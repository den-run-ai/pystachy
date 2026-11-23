# Base's field holds the object of whichever iterator class iter(xs) makes: Base is a class
# template, each of whose specializations is a class of its own, which Sub, without an __init__
# of its own, extends: Sub([1]) is of the specialization of Sub that derives from Base's (#962)
class Base:
    def __init__(self, xs: list[int]) -> None:
        self.it = iter(xs)


class Sub(Base):
    pass


print(next(Sub([1]).it))
