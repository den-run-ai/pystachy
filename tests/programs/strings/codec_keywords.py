# str.encode() and bytes.decode() with encoding and errors given by name, in that order, and with
# errors alone (encoding's default, UTF-8); the arguments are evaluated in the order written
import sys


def note(label: str, value: str) -> str:
    print("evaluate", label)
    return value


raw = sys.argv[0].encode()[:0] + b"caf\xc3\xa9 \xff!"
print(repr(raw.decode(errors="replace")))
print(repr(raw.decode("utf-8", errors="ignore")))
print(repr(raw.decode(encoding="latin-1")))
print(repr(raw.decode(encoding="ascii", errors="backslashreplace")))
print(repr(raw.decode(encoding=note("encoding", "utf-8"), errors=note("errors", "surrogateescape"))))
print(repr(raw.decode(errors=note("errors alone", "replace"))))
try:
    raw.decode(encoding="utf-8")
except UnicodeDecodeError as e:
    print("UnicodeDecodeError:", e)
handler = "xmlcharrefreplace"
text = "café €"
print(text.encode(errors="strict"))
print(text.encode("ascii", errors=handler))
print(text.encode(encoding="latin-1", errors="replace"))
print(text.encode(encoding=note("encoding", "ascii"), errors=note("errors", "ignore")))
print("\ud800".encode(errors="surrogatepass"))
try:
    text.encode(encoding="ascii")
except UnicodeEncodeError as e:
    print("UnicodeEncodeError:", e)
