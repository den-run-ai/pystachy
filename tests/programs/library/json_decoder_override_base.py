"""Base-typed decoder dispatch preserves whitespace, positions and first errors."""
import json


class Decoder(json.JSONDecoder):
    def __init__(self, end: int) -> None:
        self.end = end
        self.calls = 0

    # The common recursive return contract permits dispatch through the base.
    # Quoting keeps this Pystachy annotation valid with CPython's json module.
    def raw_decode(self, s: str, *, idx: int = 0) -> "tuple[json.JSONValue, int]":
        self.calls += 1
        print("raw", idx, repr(s))
        return 42, self.end


class FailingDecoder(json.JSONDecoder):
    def __init__(self, unicode_error: bool) -> None:
        self.unicode_error = unicode_error
        self.calls = 0

    def raw_decode(self, s: str, idx: int = 0) -> "tuple[json.JSONValue, int]":
        self.calls += 1
        print("raising", idx)
        if self.unicode_error:
            raise UnicodeDecodeError("ascii", b"\xff", 0, 1, "decoder override")
        raise ValueError("decoder override")


def through_base(decoder: json.JSONDecoder, text: str):
    return decoder.decode(text)


print("default", json.dumps(through_base(json.JSONDecoder(), " \n[1, false] \t")))
for text, end in [(" \t\nnull \r", 7), ("\u2003null", 5), (" \né🌲 \tX", 4), ("null\u2003", 4)]:
    decoder = Decoder(end)
    try:
        print("value", through_base(decoder, text))
    except json.JSONDecodeError as error:
        print("json error", error.msg, error.pos, error.lineno, error.colno)
    print("calls", decoder.calls)

# CPython's trailing-whitespace regex clamps the custom end before matching.
for end in [-5, 0, 1, 2, 3, 8]:
    decoder = Decoder(end)
    try:
        print("end", end, through_base(decoder, " x"))
    except json.JSONDecodeError as error:
        print("end error", end, error.msg, error.pos)
    print("calls", decoder.calls)

for unicode_error in [False, True]:
    failing = FailingDecoder(unicode_error)
    try:
        through_base(failing, " \nnull")
    except UnicodeDecodeError as error:
        print("unicode error", error)
    except ValueError as error:
        print("value error", error)
    print("failed calls", failing.calls)
