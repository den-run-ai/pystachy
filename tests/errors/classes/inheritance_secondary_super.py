# error: super() in a primary hierarchy with a secondary base is not supported
# super() in the primary hierarchy may not call a method that a secondary base defines too:
# CPython's method resolution order puts the secondary base after the primary's bases, where
# such a call can find it (tests/programs/classes/inheritance_secondary_super_calls.py: one it lacks).
class Root:
    def action(self) -> int:
        return 1


class First(Root):
    def action(self) -> int:
        return super().action()


class Second:
    def action(self) -> int:
        return 2


class Bad(First, Second):
    pass
