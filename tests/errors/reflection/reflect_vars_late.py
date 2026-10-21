# error: reflect_vars_late.py:14: error: vars() of A is not supported: its attribute y, which its __init__ may leave unassigned, may be assigned later, which inserts it last in the __dict__ (#486)
class A:
    def __init__(self, f: bool) -> None:
        self.x = 1
        if f:
            self.y = 2
        self.z = 3


a = A(False)
a.y = 5
# CPython's __dict__ is then {'x': 1, 'z': 3, 'y': 5}: the order depends on where y was first
# assigned, which the compiler does not know
print(vars(a))
