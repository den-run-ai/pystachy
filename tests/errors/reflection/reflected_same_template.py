# error: reflected_same_template.py:12: error: unsupported operand type(s) for &: 'Box' and 'Box'
# Box[int] and Box[str] are one class to CPython, which calls __rand__ only for a right operand of
# another class, so it raises this TypeError
class Box:
    def __init__(self, v):
        self.v = v

    def __rand__(self, o: int) -> int:
        return o


print(Box(1) & Box("x"))
