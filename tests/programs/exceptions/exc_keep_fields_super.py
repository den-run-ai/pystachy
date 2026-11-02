# An exception class whose __init__ assigns its fields and then calls super().__init__() shows
# only that call's arguments in str(e) and repr(e), as json.JSONDecodeError does; the fields it
# read in that call's argument (self.lineno) are its own. A KeyError's str(e) is its key's repr.
class DocError(ValueError):
    def __init__(self, msg: str, doc: str, pos: int) -> None:
        self.msg: str = msg
        self.doc: str = doc
        self.pos: int = pos
        self.lineno: int = doc.count("\n", 0, pos) + 1
        super().__init__(f"{msg}: line {self.lineno} (char {pos})")


class NoKey(KeyError):
    def __init__(self, key: str, table: str) -> None:
        self.table = table
        super().__init__(key)


class Pair(Exception):
    def __init__(self, a: int, b: int) -> None:
        self.total = a + b
        super().__init__(*(a, b))


e = DocError("Expecting value", "ab\ncdé" * 3, 4)
print(str(e))
print(repr(e))
print(e.msg, e.pos, e.lineno, len(e.doc))
k = NoKey("a'b", "t")
print(str(k), repr(k), k.table)
m = Pair(1, 2)
print(str(m), repr(m), m.total)
try:
    raise DocError("Bad", "x\ny", 2)
except ValueError as err:
    print("caught", err, repr(err))
raise DocError("Unterminated string", "\n\n\"abc", 2)
