# The only try statements of a program are in the methods of exception classes: the program
# still has exceptions on (their landing pads need the passes and pys_eh_on).
class E(Exception):
    def __init__(self, s: str) -> None:
        try:
            n = int(s)
        except ValueError:
            n = 0
        super().__init__(n)

    def __str__(self) -> str:
        try:
            return "E" + str(int(str(self.args_text())))
        except ValueError:
            return "bad"
        finally:
            pass

    def args_text(self) -> str:
        try:
            return "1"
        finally:
            pass


class F(E):
    def __repr__(self) -> str:
        try:
            return str(int("x"))
        except ValueError:
            return "F?"


print(repr(E("7")), repr(E("x")), str(E("2")), E("3").args_text(), repr(F("4")), str(F("5")))
raise F("6")
