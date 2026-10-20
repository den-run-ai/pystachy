# Once an IncrementalNewlineDecoder has decoded more than one kind of newline, CPython's newlines
# is a tuple of them, which Pystachy's (str | None) is not: its newlines raises NotImplementedError,
# as TextIOWrapper's does. What decode() returns is CPython's.
import io

d = io.IncrementalNewlineDecoder(None, True)
print(repr(d.decode("a\nb\r\n", True)))
try:
    print(d.newlines)
except NotImplementedError as e:
    print("NotImplementedError:", e)
