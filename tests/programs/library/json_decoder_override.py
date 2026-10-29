"""Inherited and unbound decode must execute a concrete raw_decode override."""
import json


class Decoder(json.JSONDecoder):
    def __init__(self) -> None:
        self.calls = 0

    def raw_decode(self, s: str, *, idx: int = 0) -> tuple[int, int]:
        self.calls += 1
        print("raw", idx, repr(s))
        return 42, len(s)


decoder = Decoder()
print("direct", decoder.decode(" \t\nnull"), decoder.calls)
print("unbound", json.JSONDecoder.decode(decoder, " \rnull"), decoder.calls)
print("empty", decoder.decode(""), decoder.calls)
