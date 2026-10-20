class Base:
    def read(self) -> str:
        return "base"


class Child(Base):
    def read(self) -> str:
        return "child"


class Other:
    def read(self) -> str:
        return "other"


def check(value: Base | Other | None) -> None:
    print(isinstance(value, Base), isinstance(value, Child), isinstance(value, Other))
    print(isinstance(value, (Child, Other)), isinstance(value, type(None)))
    print(isinstance(value, Child | None), isinstance(value, (Child, (Other, type(None)))))
    if value is not None:
        print(value.read())
    if isinstance(value, Base):
        print(value.read(), isinstance(value, Child))
    elif isinstance(value, Other):
        print(value.read())
    else:
        print("none")


items: list[Base | Other | None] = [Base(), Child(), Other(), None]
for item in items:
    check(item)
