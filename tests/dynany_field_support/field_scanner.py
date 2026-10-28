# This module deliberately uses ordinary typed storage, without dynamic Any: a scanner whose
# methods copy a numeric field into locals and write it back, as json's _Parser does.
class Scanner:
    def __init__(self, text: bytes, start: int) -> None:
        self.data = text
        self.pos = start
        self.n = len(text)

    def skip(self) -> None:
        # the field in a local, advanced past spaces, and written back
        data = self.data
        n = len(data)
        i = self.pos
        while i < n:
            c = data[i]
            if c != 32:
                break
            i += 1
        self.pos = i

    def word(self) -> int:
        # the end of the word at pos, which becomes pos; the local is passed to a call first
        begin = self.pos
        end = self.end_of(begin)
        self.pos = end
        return begin

    def end_of(self, begin: int) -> int:
        i = begin
        while i < self.n and self.data[i] != 32:
            i += 1
        return i

    def peek(self) -> int:
        at = self.pos
        return at
