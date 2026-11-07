# Input code points exercise the native escaping pass without constant folding. A custom
# repr exposes its empty/ASCII paths and encoded surrogates before string repr escapes them.
class RawRepr:
    def __init__(self, text: str):
        self.text = text

    def __repr__(self) -> str:
        return self.text


saved: list[str] = []
for case in range(7):
    text = "".join(chr(int(part, 16)) for part in input().split())
    obj = RawRepr(text)
    escaped = ascii(obj)
    saved.append(escaped)
    print(case, ascii(text), repr(escaped), repr(f"{obj!a}"), repr("{!a}".format(obj)))

# Long ASCII runs before, between and after escapes use bulk copies. Retain the results
# across later allocations so program-only GC stress checks the returned strings too.
for text in ["a" * 257, "a" * 257 + "é", "€" + "b" * 257, "c" * 257 + "😀" + "d" * 257 + "é"]:
    escaped = ascii(RawRepr(text))
    saved.append(escaped)
    print(len(escaped), repr(escaped))
print([len(s) for s in saved], [s.isascii() for s in saved])
