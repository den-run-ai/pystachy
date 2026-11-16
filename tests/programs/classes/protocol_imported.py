# A Protocol of an imported module: the program's own classes implement it.
from ifaceshapes import Line, Measured, total


class Word:
    def __init__(self, text: str) -> None:
        self.text = text

    def size(self) -> int:
        return len(self.text)


items: list[Measured] = [Line(3), Word("four")]
print(total(items), [m.size() for m in items])
