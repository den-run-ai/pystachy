# A list subclass with an attribute of its own and its own __str__ and __repr__, as the email
# package's TokenList has: __init__ calls list's, with and without items, and sets a field;
# str() is the class's, and its repr wraps list's own.


class Terminal:
    def __init__(self, value: str, token_type: str) -> None:
        self.value = value
        self.token_type = token_type

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return "{}({!r})".format(self.token_type, self.value)


class TokenList(list):
    token_type = "token-list"
    syntactic_break = True

    def __init__(self, tokens: list[Terminal]) -> None:
        super().__init__(tokens)
        self.defects: list[str] = []

    def __str__(self) -> str:
        return "".join(str(x) for x in self)

    def __repr__(self) -> str:
        return "{}({})".format(self.__class__.__name__, super().__repr__())

    @property
    def value(self) -> str:
        return "".join(x.value for x in self if x.value)

    @property
    def all_defects(self) -> list[str]:
        return self.defects + ["{}: empty".format(x.token_type) for x in self if not x.value]

    def startswith_fws(self) -> bool:
        return self[0].token_type == "fws"

    def pop_trailing_ws(self) -> None:
        if self and self[-1].token_type == "fws":
            self.pop()


class Words(list):
    def __init__(self) -> None:
        super().__init__()
        self.count = 0

    def add(self, w: str) -> None:
        self.append(w)
        self.count += len(w)


tl = TokenList([Terminal(" ", "fws"), Terminal("hello", "atext"), Terminal("", "ptext"), Terminal("  ", "fws")])
print(str(tl) + "|")
print(repr(tl))
print(tl)
print(f"{tl}|{tl!r}|{tl!s}|")
print(tl.value + "|", tl.all_defects, tl.defects, tl.token_type, tl.syntactic_break)
print(tl.startswith_fws(), len(tl))
tl.pop_trailing_ws()
tl.pop_trailing_ws()
tl.defects.append("trailing whitespace")
print(len(tl), tl.all_defects)
tl.append(Terminal("!", "atext"))
print(str(tl), [str(t) for t in tl], [tl])
ws = Words()
for w in "a list subclass".split():
    ws.add(w)
print(ws, ws.count, len(ws), " ".join(ws), ws == ["a", "list", "subclass"])
both = [Words(), ws]
print(both, [len(x) for x in both], both[1].count)
