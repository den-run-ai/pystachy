# error: class_nested_scope_base.py:16: error: class Outer.Inner is not supported: its decorators or bases read Base, which the body of class Outer binds before it, and Pystachy makes a nested class before the class around it
# CPython evaluates a nested class's bases in the scope of the class body around it, where Base
# is Other here (it prints "other"); Pystachy, which makes the nested class first, would read
# the module's Base.
class Base:
    tag = "module"


class Other:
    tag = "other"


class Outer:
    Base = Other

    class Inner(Base):
        pass


print(Outer.Inner.tag)
