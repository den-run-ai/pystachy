# The text of getattr() with a name only the run time knows (#489's first version): print() of it
class C:
    def __init__(self) -> None:
        self.a = 1


name = "a"
print(getattr(C(), name))
