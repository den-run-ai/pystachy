# Making an exception formats none of its arguments where its __init__ assigns fields and then
# calls super().__init__(), which keeps that call's arguments (made: no repr of doc); one whose
# __init__ reads str(self) first keeps them as it is made (kept: the repr of the tuple).
class DocError(ValueError):
    def __init__(self, msg: str, doc: str, pos: int) -> None:
        self.msg = msg
        self.doc = doc
        self.pos = pos
        super().__init__(f"{msg}: char {self.pos}")


class Early(ValueError):
    def __init__(self, msg: str, doc: str) -> None:
        self.before = str(self)
        super().__init__(msg)


def made(doc: str) -> DocError:
    return DocError("Expecting value", doc, 3)


def kept(doc: str) -> Early:
    return Early("Expecting value", doc)


print(made("x").pos, kept("y").before)
