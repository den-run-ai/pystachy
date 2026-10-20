# iniconfig's parser (_parse.py) and ParseError: the cases of its own test suite
# (testing/test_iniconfig.py of iniconfig 2.3.1), run as a program instead of under pytest
from iniconfig import ParseError
from iniconfig import iscommentline
from iniconfig._parse import ParsedLine as PL
from iniconfig._parse import parse_ini_data
from iniconfig._parse import parse_lines

check_tokens: dict[str, tuple[str, list[PL]]] = {
    "section": ("[section]", [PL(0, "section", None, None)]),
    "value": ("value = 1", [PL(0, None, "value", ["1"])]),
    "value in section": (
        "[section]\nvalue=1",
        [PL(0, "section", None, None), PL(1, "section", "value", ["1"])],
    ),
    "empty value": ("value =", [PL(0, None, "value", [])]),
    "value with continuation": (
        "names =\n Alice\n Bob",
        [PL(0, None, "names", ["Alice", "Bob"])],
    ),
    "value with aligned continuation": (
        "names = Alice\n        Bob",
        [PL(0, None, "names", ["Alice", "Bob"])],
    ),
    "continuations on several values": (
        "a = 1\n 2\n\n 3\n[s]\nb =\n x\n y\nc = z",
        [
            PL(0, None, "a", ["1", "2", "3"]),
            PL(4, "s", None, None),
            PL(5, "s", "b", ["x", "y"]),
            PL(8, "s", "c", ["z"]),
        ],
    ),
    "blank line": (
        "[section]\n\nvalue=1",
        [PL(0, "section", None, None), PL(2, "section", "value", ["1"])],
    ),
    "comment": ("# comment", []),
    "comment on value": ("value = 1", [PL(0, None, "value", ["1"])]),
    "comment on section": ("[section] #comment", [PL(0, "section", None, None)]),
    "comment2": ("; comment", []),
    "comment2 on section": ("[section] ;comment", [PL(0, "section", None, None)]),
    "pseudo section syntax in value": (
        "name = value []",
        [PL(0, None, "name", ["value []"])],
    ),
    "assignment in value": ("value = x = 3", [PL(0, None, "value", ["x = 3"])]),
    "use of colon for name-values": ("name: y", [PL(0, None, "name", ["y"])]),
    "use of colon without space": ("value:y=5", [PL(0, None, "value", ["y=5"])]),
    "equality gets precedence": ("value=xyz:5", [PL(0, None, "value", ["xyz:5"])]),
}


def parse(input: str) -> list[PL]:
    return parse_lines("sample", input.splitlines(True))


def parse_a_error(input: str) -> ParseError:
    try:
        parse(input)
    except ParseError as e:
        return e
    else:
        raise ValueError(input)


# test_tokenize
for name in sorted(check_tokens):
    text, expected = check_tokens[name]
    parsed = parse(text)
    print(f"tokenize {name!r}: {parsed == expected}")
    print("   ", parsed)

# test_parse_empty
print("empty:", parse(""), not parse(""))

# test_ParseError
e = ParseError("filename", 0, "hello")
print("ParseError:", str(e), repr(e), e.path, e.lineno, e.msg)

# continuation and section errors
for text in [" Foo", "[section]\n Foo", "[]", "!!", "[s]\nx=1\n y\n[t]\n z", "[s\n"]:
    err = parse_a_error(text)
    print(f"error {text!r}: lineno {err.lineno}: {err}")

# test_iscommentline_true, and some false ones
for line in ["#qwe", "  #qwe", ";qwe", " ;qwe", "qwe", " q#", ""]:
    print(f"iscommentline({line!r}) = {iscommentline(line)}")

# parse_ini_data: sections and the line of each name, with and without stripping
data = "﻿[section1]\nname1 = value1 # a comment\nname2 = value2 ; another\nlist = a, b, c # items\n[section2]\nnames =\n    Alice # first\n    Bob\n"
for strip in [False, True]:
    sections, sources = parse_ini_data("test.ini", data, strip_inline_comments=strip)
    print("strip" if strip else "keep", sections)
    print("   ", list(sources.items()))

# duplicate names and sections, and a value before any section
for text in ["[a]\nx = 1\nx = 2", "[a]\n[a]", "x = 1"]:
    try:
        parse_ini_data("dup.ini", text, strip_inline_comments=False)
        print("no error for", repr(text))
    except ParseError as e:
        print(f"ParseError: {e} (msg {e.msg!r})")

# the error escapes as CPython reports it
parse_ini_data("last.ini", "[s]\n = \n[s]", strip_inline_comments=True)
