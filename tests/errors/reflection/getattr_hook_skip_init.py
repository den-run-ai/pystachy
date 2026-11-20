# error: getattr_hook_skip_init.py:19: error: field 'tag' of Base may be unassigned where it is read (an object of Careful, which derives from it, may lack it), and CPython then calls __getattr__, which returns int, not the field's str: not supported (assign the field on every path of each __init__, before the object is used)
# A derived __init__ that does not call its base's leaves the base's fields unassigned, and
# CPython's read of one then gives what __getattr__ returns (#1536): Pystachy rejects the read
# where that is not a value of the field's type, also through the base class.
class Base:
    def __init__(self, tag: str) -> None:
        self.tag = tag

    def __getattr__(self, name: str) -> int:
        return len(name)


class Careful(Base):
    def __init__(self) -> None:
        self.label = "careful"


def show(b: Base) -> None:
    print(b.tag)


show(Base("b"))
show(Careful())
