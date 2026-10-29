# pystachy: dynamic-any
# A scanner's position field copied into locals, advanced, passed to calls and written back
# (json's _Parser shape) boxes no number: Scan.skip, Scan.end_of and Scan.word call no
# pys_dyn_int_box or pys_dyn_int, and items only boxes what crosses into its list[Any].
from typing import Any


class Scan:
    def __init__(self, text: bytes) -> None:
        self.data = text
        self.pos = 0
        self.n = len(text)

    def skip(self) -> None:
        data = self.data
        n = len(data)
        i = self.pos
        while i < n:
            c = data[i]
            if c != 32:
                break
            i += 1
        self.pos = i

    def end_of(self, begin: int) -> int:
        data = self.data
        i = begin + 1
        while i < self.n and data[i] != 34:
            i += 1
        return i

    def word(self) -> str:
        begin = self.pos
        end = self.end_of(begin)
        self.pos = end + 1
        start = begin + 1
        return self.cut(start, end)

    def cut(self, start: int, end: int) -> str:
        return self.data[start:end].decode()


def items(s: Scan) -> list[Any]:
    out: list[Any] = []
    while s.pos < s.n:
        s.skip()
        i = s.pos
        if i == s.n or s.data[i] != 34:
            break
        out.append(s.word())
    return out


print(len(items(Scan(b' "a" "bc"  "d"'))))
