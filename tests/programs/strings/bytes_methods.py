# bytes methods with ASCII whitespace and case, bytes() of each form, bytes.fromhex(), hex(),
# str.encode() and bytes.decode() round trips, and the errors they raise
b = b"  Hello, World  "
print(b.strip(), b.lstrip(), b.rstrip(), b.strip(b" H"), b"xxhixx".strip(b"x"))
print(b.upper(), b.lower(), b.swapcase(), b"hello world".capitalize())
w = b"a,b,,c"
print(w.split(b","), w.split(b",", 1), w.rsplit(b",", 1), b"  a b \t c\n".split(), b"a  b".split(None, 1))
print(b"-".join([b"x", b"y", b"z"]), b"".join([]), b", ".join((b"p", b"q")))
print(w.find(b","), w.rfind(b","), w.find(b"z"), w.index(b"b"), w.rindex(b","), w.count(b","), w.count(b""))
print(w.startswith(b"a,"), w.endswith(b"c"), w.startswith(b"b", 2), w.endswith((b"x", b"c")))
print(w.replace(b",", b";"), w.replace(b",", b"", 2), w.partition(b","), w.rpartition(b","), w.partition(b"z"))
print(b"prefix-body".removeprefix(b"prefix-"), b"body.txt".removesuffix(b".txt"))
print(b"abc".isalpha(), b"a1".isalnum(), b"123".isdigit(), b"  ".isspace(), b"ABC".isupper(), b"abc".islower(), b"\xff".isascii(), b"ab".isascii())
print(b"x".ljust(3), b"x".rjust(3, b"*"), b"x".center(5, b"-"), b"42".zfill(5), b"-7".zfill(4))
print(b"l1\nl2\r\nl3\rl4".splitlines(), b"a\nb\n".splitlines(True), b"x\x0by".splitlines())
print(b"\xde\xad\xbe\xef".hex(), b"".hex(), bytes.fromhex("dead beef"), bytes.fromhex(""))
print(bytes(), bytes(3), bytes([65, 66, 67]), bytes(b"copy"), bytes("hé", "utf-8"), bytes("abc", "ascii"))
print("héllo".encode(), "héllo".encode("utf-8"), "abc".encode("ascii"), "hé".encode("latin-1"))
print(b"h\xc3\xa9llo".decode(), b"h\xc3\xa9llo".decode("utf-8"), b"abc".decode("ascii"), b"h\xe9".decode("latin-1"))
print(b"a\xffb".decode("utf-8", "replace"), b"a\xffb".decode("utf-8", "ignore"), b"a\xffb".decode("ascii", "backslashreplace"))
print(repr(b"a\xffb".decode("utf-8", "surrogateescape").encode("utf-8", "surrogateescape")))
print("€".encode("ascii", "replace"), "€".encode("ascii", "ignore"), "€".encode("latin-1", "backslashreplace"), "€".encode("ascii", "xmlcharrefreplace"))
for bad in [b"\xff", b"a\xc3", b"\xed\xa0\x80"]:
    try:
        bad.decode("utf-8")
    except UnicodeDecodeError as e:
        print("UnicodeDecodeError:", e)
try:
    "€".encode("ascii")
except UnicodeEncodeError as e:
    print("UnicodeEncodeError:", e)
try:
    bytes([256])
except ValueError as e:
    print("ValueError:", e)
try:
    bytes.fromhex("zz")
except ValueError as e:
    print("ValueError:", e)
print(isinstance(b"x", bytes), isinstance("x", bytes), sum(b"\x01\x02"), max(b"az"), sorted(b"cab"))
