# error: del of an attribute is only supported for a property (which calls its deleter)
class C:
    def __init__(self) -> None:
        self.x = 1


c = C()
del c.x
