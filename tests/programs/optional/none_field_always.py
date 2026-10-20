# A field that nothing gives another value than None is None: printed, compared, in
# vars(), also in a class template's specialization for a None argument (as reprlib's
# Repr(indent=None)), and given by a call that returns None.
def setup() -> None:
    print("setup")


class Config:
    def __init__(self) -> None:
        self.hook = None
        self.ready = setup()
        self.level = 3

    def describe(self) -> str:
        if self.hook is None:
            return f"level {self.level}, no hook"
        return "hook"


class Repr:
    def __init__(self, maxlevel=6, indent=None):
        self.maxlevel = maxlevel
        self.indent = indent

    def show(self) -> str:
        if self.indent is None:
            return f"flat, {self.maxlevel} levels"
        return "indented"


c = Config()
print(c.describe(), c.hook, c.ready)
print(c.hook is None, c.hook == None, vars(c))
r = Repr()
print(r.show(), r.indent, repr(r.indent))
print(Repr(2).show())
