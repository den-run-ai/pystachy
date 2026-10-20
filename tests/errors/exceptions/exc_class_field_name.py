# error: a field 'name' of exception class NotFound is not supported here: AttributeError.__init__() sets its attribute name as it runs
class NotFound(AttributeError):
    def __init__(self, n: str) -> None:
        self.name = n
        super().__init__("not found: " + n)


print(NotFound("x").name)
