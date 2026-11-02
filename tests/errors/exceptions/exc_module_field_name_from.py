# error: a field 'name_from' of exception class M is not supported here: ImportError.__init__() sets its attribute name_from as it runs, after what assigned the field before it (assign self.name_from in __init__, after super().__init__(...))
class M(ModuleNotFoundError):
    def __init__(self, mod: str) -> None:
        self.name_from: str = "x"
        super().__init__("no " + mod)


m = M("m")
print(str(m), repr(m), m.name_from)
