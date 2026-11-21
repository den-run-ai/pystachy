# __getattr__ (#1536) in a program with no try statement: a property's getter that raises
# AttributeError calls the method, so the read needs exception handling.
class Lazy:
    def __init__(self) -> None:
        self.loaded = False

    @property
    def rows(self) -> int:
        if not self.loaded:
            raise AttributeError("not loaded")
        return 9

    def __getattr__(self, name: str) -> int:
        return len(name)


z = Lazy()
print(z.rows, z.other)
z.loaded = True
print(z.rows)
