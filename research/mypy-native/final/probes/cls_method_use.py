from typing import Final
class Tok:
    KW: Final = {"if", "else"}
    PREC: Final = {"+": 1, "*": 2}
    def is_kw(self, s: str) -> bool:
        return s in self.KW
    def prec(self, s: str) -> int:
        return Tok.PREC[s]
t = Tok()
print(t.is_kw("if"), t.is_kw("x"), t.prec("*"))
