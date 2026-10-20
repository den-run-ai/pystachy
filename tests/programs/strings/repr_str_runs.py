# repr() of a str copies each run of printable ASCII at once: runs that end at either quote, a
# backslash, a control character, DEL or a non-ASCII character, at the start, middle and end of a
# string, and long strings whose repr outgrows its buffer more than once
cases = ["", "a", "plain text", "it's", 'say "hi"', "both ' and \"", "back\\slash", "\\", "'", '"',
         "tab\there", "\x00lead", "trail\x1f", " ~\x7f ", "\x7f\x7f\x7f", "café au lait",
         "日本語 text", "\U0001f600!", "line1\nline2\r\n", "\x1b[0m", "~ \x20\x7e\x1f\x80"]
for s in cases:
    print(repr(s))
print(cases)
print(("tuple's", 'pair"'), {"key's": ["v\\1", "v\t2"]})
long_ascii = "abcdefghijklmnopqrstuvwxyz0123456789 " * 3000
r = repr(long_ascii)
print(len(r), r[:40], r[-40:])
mixed = ("x" * 1000 + "'" + "y" * 999 + "\\" + "\n") * 50
r = repr(mixed)
print(len(r), r.count("\\"), r[:5], r[-8:])
quotes = ("'" * 100 + "z" * 100) * 20
r = repr(quotes)
print(len(r), r[:3], r[-3:])
both = ("'\"" + "w" * 30) * 100
r = repr(both)
print(len(r), r[:8], r[-6:])
every = "".join(["ab" + chr(c) + "cd" for c in range(128)])
print(repr(every))
print(f"{long_ascii[:50]!r} {[mixed[:1003]]!r}")
d: dict[str, int] = {}
try:
    print(d["it's a \"key\"\n" + "k" * 30])
except KeyError as e:
    print("KeyError", e)
