# error: class_as_value.py:7: error: class 'C' cannot be used as a value
class C:
    def __init__(self) -> None:
        self.k = 4


print(C)
