# error: type object 'C' has no attribute 'v' (its objects have the field 'v')
class C:
    def __init__(self) -> None:
        self.v = 1


print(C().v, C.v)
