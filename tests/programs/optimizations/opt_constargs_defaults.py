# Arguments that every call leaves at one constant (constargs, docs/typed-ir.md): the tests of
# them are decided, here where they are not, and through calls that pass them on. Each
# function prints what its branches do, so a branch decided wrongly shows.


class Report:
    def __init__(self, title: str, width: int = 0, upper: bool = False) -> None:
        self.title: str = title.upper() if upper else title
        self.width = width

    def line(self, text: str, mark: str | None = None, indent: int = 0) -> str:
        out = " " * indent + text
        if mark is not None:
            out = mark + out
        if self.width:
            out = out.ljust(self.width, ".")
        return self.title + ": " + out


def shout(text: str, loud: bool = False, times: int = 1, tail: str | None = None) -> str:
    if loud:
        text = text.upper()
    if times != 1:
        text = text * times
    if tail is not None:
        text += tail
    return text


def relay(text: str, loud: bool = False, tail: str | None = None) -> str:
    # passes its own on: decided only while every call of relay leaves them
    return shout(text, loud, tail=tail)


def always(text: str, loud: bool = False) -> str:
    # every call passes True: the constant is not the default
    return shout(text, loud)


def count_down(n: int, verbose: bool = False, depth: int = 0) -> int:
    if verbose:
        print("  " * depth + str(n))
    if n == 0:
        return depth
    return count_down(n - 1, verbose, depth + 1)


def pick(key: str, table: dict[str, int] | None = None, fallback: int = -1) -> int:
    if table is None:
        table = {"a": 1}
    if key in table:
        return table[key]
    return fallback


def late(flag: bool = False) -> str:
    # its one caller that passes True runs last, and only from another function
    return "late:on" if flag else "late:off"


def turn_on() -> str:
    return late(True)


def main() -> None:
    print(shout("a"), shout("b", times=2), shout("c", tail="!"))
    print(relay("d"), relay("e"), always("f", True), always("g", True))
    print(count_down(3), count_down(2))
    print(pick("a"), pick("z"), pick("z", fallback=7), pick("k", {"k": 5}))
    quiet = Report("r")
    wide = Report("w", 6)
    print(quiet.line("x"), wide.line("y"), quiet.line("z", indent=2))
    print(late(), late())
    print(turn_on())
    print(count_down(1, True))


main()
