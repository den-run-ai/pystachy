# __getattr__ (#1536) in a program with no try statement and no reflective lookup of a property:
# hasattr() and getattr() with a default still catch the method's AttributeError, so the program
# is compiled with exception handling.
class Conf:
    def __init__(self) -> None:
        self.data = {"port": 80}

    def __getattr__(self, name: str) -> int:
        if name not in self.data:
            raise AttributeError(name)
        return self.data[name]


c = Conf()
print(c.port, hasattr(c, "port"), hasattr(c, "depth"), getattr(c, "depth", 3), getattr(c, "port", 3))
