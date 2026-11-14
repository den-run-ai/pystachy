# x in xs, xs.index(x) and xs.count(x) of a list of strs for an x that may be None, and of a
# list that holds None: None is in no list of strs, and equals only None.
import sys

DELIMITERS: list[str] = ['"', "'", "“", "”"]


def char_at(text: str, i: int) -> str | None:
    return text[i] if 0 <= i < len(text) else None


def find(xs: list[str], x: str | None) -> int:
    if x is None:
        return -2
    return xs.index(x) if x in xs else -1


def main() -> None:
    text = "a\"b'c“d”" + "".join(sys.argv[1:])
    hits = 0
    for i in range(-1, len(text) + 2):
        ch = char_at(text, i)
        if ch in DELIMITERS:
            hits += 1
        if ch not in DELIMITERS and ch is not None and ch in "bd":
            hits += 10
    print(hits, None in DELIMITERS, char_at("", 0) in DELIMITERS, char_at('"', 0) in DELIMITERS)
    made = "".join(["“", ""])
    print(DELIMITERS.count(made), DELIMITERS.count("x"), find(DELIMITERS, made), find(DELIMITERS, "z"), find(DELIMITERS, None))
    mixed: list[str | None] = ["a", None, "b", None]
    for x in [char_at("a", 0), char_at("a", 5), char_at("c", 0), char_at("b", 0)]:
        print(repr(x), x in mixed, mixed.count(x), mixed.index(x) if x in mixed else -1)
    empty: list[str] = []
    print(char_at("q", 0) in empty, char_at("q", 3) in empty, empty.count("q"))


main()
