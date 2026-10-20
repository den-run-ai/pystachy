# With an __init__ of the program that does not call super().__init__(), an object of a class
# deriving from OSError has no args (OSError.__new__ leaves them to OSError.__init__), and one
# deriving from SystemExit has the code None (SystemExit.__init__ sets it), so raising it ends
# the program with status 0 and no output.
class FE(OSError):
    def __init__(self, p: str, q: str):
        super().__init__(p + q)
        self.p = p


class GE(FileNotFoundError):
    def __init__(self, p: str):
        self.p = p


class Quit(SystemExit):
    def __init__(self, n: int):
        self.n = n


class Stop(SystemExit):
    def __init__(self, n: int):
        super().__init__(n + 1)


e = FE("a", "b")
print(repr(e), str(e))
print(repr(GE("x")), str(GE("x")) == "", GE("y").p)
try:
    raise GE("z")
except OSError as o:
    print("caught", repr(o))
try:
    raise Stop(3)
except SystemExit as q:
    print(repr(q), str(q))
try:
    raise Quit(5)
except SystemExit as q:
    print(repr(q), str(q))
raise Quit(7)
