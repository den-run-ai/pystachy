# __getattr__ (#1536) in a program with no try statement: the text of getattr() with a default
# and a name only the run time knows catches the method's AttributeError.
import sys


class Conf:
    def __init__(self) -> None:
        self.data = {"a1": 1}

    def __getattr__(self, name: str) -> int:
        if name not in self.data:
            raise AttributeError(name)
        return self.data[name]


c = Conf()
for n in sys.argv[1:] + ["data"]:
    print(n, getattr(c, n, "none"), hasattr(c, n))
