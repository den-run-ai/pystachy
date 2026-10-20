# io.IncrementalNewlineDecoder without a decoder, as CPython's C one decodes: \r, \n and \r\n
# anywhere in a chunk or split between two, a final \r held back until the next call or a final
# one, translation or not, the newlines decoded, and its state
import io


def show(d: io.IncrementalNewlineDecoder, chunks: list[str], last: bool) -> None:
    out: list[str] = []
    for c in chunks:
        out.append(d.decode(c))
    out.append(d.decode("", last))
    print(out, repr(d.newlines), d.getstate())


show(io.IncrementalNewlineDecoder(None, True), ["a\r", "\nb"], False)
show(io.IncrementalNewlineDecoder(None, False), ["a\r", "\nb"], False)
show(io.IncrementalNewlineDecoder(None, True), ["a\r"], False)
show(io.IncrementalNewlineDecoder(None, True), ["a\r"], True)
show(io.IncrementalNewlineDecoder(None, False), ["x\ry\r"], True)
show(io.IncrementalNewlineDecoder(None, True), ["one\ntwo\n", "three\n"], True)
show(io.IncrementalNewlineDecoder(None, False), ["\r\n\r\n", "", "\r", "\n"], True)
show(io.IncrementalNewlineDecoder(None, True), ["\r\r", "\x00\r"], True)
show(io.IncrementalNewlineDecoder(None, False), ["\r\n\x00", "\t\r", "\n"], False)
show(io.IncrementalNewlineDecoder(None, True), ["café\r", "\U0001f600"], True)
show(io.IncrementalNewlineDecoder(None, True), ["", ""], False)

# the state: a \r held back is its flag's lowest bit, which setstate() sets and clears
d = io.IncrementalNewlineDecoder(None, True)
print(repr(d.decode("p\r")), d.getstate())
d.setstate((b"", 0))
print(repr(d.decode("\nq")), d.getstate(), repr(d.newlines))
d.reset()
d.setstate((b"", 3))
print(d.getstate(), repr(d.decode("r")), repr(d.newlines))
d.reset()
print(d.getstate(), repr(d.newlines), repr(d.decode("s\r\n", final=True)), repr(d.newlines))
d.setstate((b"x", -1))
print(d.getstate(), repr(d.decode("t", final=True)))

# translate and final are tested for truth
for t in (0, 1):
    e = io.IncrementalNewlineDecoder(None, t)
    print(t, repr(e.decode("u\r\nv\r", 1)), repr(e.decode("w\r", 0)), e.getstate())
e = io.IncrementalNewlineDecoder(None, "yes", errors="ignore")
print(repr(e.decode(input="a\rb\r", final="x")), repr(e.newlines))
