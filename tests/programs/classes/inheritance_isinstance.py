# Runtime hierarchy checks include all ancestors and distinguish siblings through a base type.
class Base:
    pass


class Left(Base):
    pass


class Deep(Left):
    pass


class Right(Base):
    pass


def report(obj: Base) -> None:
    print(isinstance(obj, Base), isinstance(obj, Left), isinstance(obj, Deep), isinstance(obj, Right))
    if isinstance(obj, Deep):
        print("deep")
    elif isinstance(obj, Left):
        print("left")
    elif isinstance(obj, Right):
        print("right")
    else:
        print("base")


for obj in [Base(), Left(), Deep(), Right()]:
    report(obj)
maybe: Base | None = Deep()
print(isinstance(maybe, Base), isinstance(maybe, Left), isinstance(maybe, Right))
maybe = None
print(isinstance(maybe, Base), isinstance(maybe, Left))
