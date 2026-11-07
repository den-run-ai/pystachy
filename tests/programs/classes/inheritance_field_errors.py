# Missing fields name the exact runtime class, even through a shared base or inherited method.
class Base:
    def __init__(self, ready: bool) -> None:
        if ready:
            self.value = 17
            self.text = "present"

    def __eq__(self, other: "Base") -> bool:
        return self.value == other.value


class Child(Base):
    pass


class Deep(Child):
    pass


class Sibling(Base):
    pass


class Other:
    def __init__(self, ready: bool) -> None:
        if ready:
            self.value = 29


class OtherChild(Other):
    pass


def show(obj: Base) -> None:
    try:
        print("value", obj.value)
    except AttributeError as error:
        print("value", error)
    try:
        print("text", obj.text)
    except AttributeError as error:
        print("text", error)
    obj.value = 31
    obj.text = "assigned"
    print("after", obj.value, obj.text)


def compare(left: Base, right: Base) -> None:
    try:
        print("equal", left == right)
    except AttributeError as error:
        print("equal", error)


def other(obj: Other) -> None:
    try:
        print("other", obj.value)
    except AttributeError as error:
        print("other", error)


objects: list[Base] = [Base(False), Child(False), Deep(False), Sibling(False), Deep(True)]
for obj in objects:
    show(obj)
compare(Child(False), Deep(True))
compare(Child(True), Deep(False))
compare(Child(True), Deep(True))
other(Other(False))
other(OtherChild(False))
other(OtherChild(True))


class Missing(Exception):
    def __init__(self, ready: bool) -> None:
        super().__init__("exception")
        if ready:
            self.value = 41


class MissingChild(Missing):
    pass


def exception_field(obj: Missing) -> None:
    try:
        print("exception", obj.value)
    except AttributeError as error:
        print("exception", error)


exception_field(Missing(False))
exception_field(MissingChild(False))
exception_field(MissingChild(True))
