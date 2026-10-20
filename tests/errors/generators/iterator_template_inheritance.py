# error: inheritance with generic class templates is not supported: an __init__ that calls iter() or takes an Iterator[T] or Iterable[T] makes one (an iterator's type is its class)
# Base's field holds the object of whichever iterator class iter(xs) makes: Base is a class
# template, each of whose specializations is a class of its own, which a subclass cannot extend
class Base:
    def __init__(self, xs: list[int]) -> None:
        self.it = iter(xs)


class Sub(Base):
    pass


print(next(Sub([1]).it))
