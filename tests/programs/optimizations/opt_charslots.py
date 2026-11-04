from typing import Any


def classify(text: str, index: int) -> int:
    char = text[index]
    if char == ":":
        return 1
    if char == "\0":
        return 2
    return 0


def returned(text: str) -> str:
    char = text[0]
    if char == ":":
        return "colon"
    return char


def boxed(text: str) -> Any:
    char = text[0]
    if char == ":":
        return "colon"
    result: Any = char
    return result


def same_object(text: str, other: str) -> bool:
    char = text[0]
    if char == ":":
        return True
    return char is other


def nonascii(text: str) -> bool:
    char = text[0]
    if char == ":":
        return True
    return char == "é"


def assigned_twice(text: str, replace: bool) -> bool:
    char = text[0]
    if replace:
        char = ":"
    return char == ":"


def conditional(text: str, defined: bool) -> bool:
    if defined:
        char = text[0]
    return char == ":"


assert conditional(":", True)
try:
    conditional(":", False)
except UnboundLocalError:
    print("unbound")


calls = 0
source = ":"


def reset(index: int) -> int:
    global source, calls
    source = "?"
    calls += 1
    return index


def ordered(index: int) -> bool:
    char = source[reset(index)]
    print("after index")
    return char == ":"


for text in [":a", "é:\0🚀\ud800"]:
    for pos in range(-len(text), len(text)):
        c = list(text)[pos]
        assert classify(text, pos) == (1 if c == ":" else (2 if c == "\0" else 0))
        assert returned(c) == ("colon" if c == ":" else c)
        assert boxed(c) == returned(c)
        assert same_object(c, "xx") == (c == ":")
        assert nonascii(c) == (c == ":" or c == "é")
        assert assigned_twice(c, True) and assigned_twice(c, False) == (c == ":")

for pos in [0, -2, 9223372036854775807, -9223372036854775808]:
    try:
        print(ordered(pos))
    except IndexError as error:
        print(str(error))
    print(source, calls)
