# A subclass's class variable shadows a field its exception base assigns: the base's __init__,
# run by super().__init__(), gives the subclass's object the field, which its class variable no
# longer shows. That assignment through the base once left the subclass's own "is assigned" flag
# unset, so the object read its class's value instead.
class Base(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)
        self.label = "base " + msg


class Sub(Base):
    label = "sub"

    def __init__(self, kept: bool) -> None:
        if kept:
            super().__init__("kept")


def relabel(b: Base, text: str) -> None:
    b.label = text


Sub.label = "changed"
s = Sub(True)
t = Sub(False)
print(s.label, t.label)
relabel(t, "assigned")
print(t.label, Sub(False).label)
