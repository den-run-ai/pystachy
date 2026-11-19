# bytearray's repr escapes a single quote whichever quotes enclose it, as CPython's does (its bytes's
# repr does not).
for x in (b"'", b'"', b"'\"", b"it's", b"\\'", b"a\nb\x00\xff"):
    print(repr(bytearray(x)), repr(x))
