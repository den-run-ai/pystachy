def direct(s: str, i: int) -> bool:
    return s[i] == ":" or " " != s[i]


def nonascii(s: str, i: int) -> bool:
    return s[i] == "é"


def several(s: str, i: int) -> bool:
    return s[i] != "::"


def chained(s: str, i: int) -> bool:
    return "/" == s[i] == "."


def from_list(parts: list[str], i: int) -> bool:
    return parts[i] == "."


print(direct(":", 0), nonascii("é", 0), several(":", 0), chained("/", -1), from_list(["."], 0))
