# Public regex positions use code points, including bounded matches and nested callbacks.
# Former Unicode deviations are checked directly against CPython, without normalizing spans.
import re

m = re.search("é", "café")
if m is not None:
    print(m.start(), m.end(), m.span(), "café"[m.start():m.end()] == m.group())
m = re.search(r"\w+", "€uro")
if m is not None:
    print(m.start(), m.end())

print(re.compile(".").match("é", 0, 1))
m = re.compile(".").search("aéb", 2)
if m is not None:
    print(m.span(), m.group(), m.pos, m.endpos)
m = re.compile(".+").search("aéb", 0, 2)
if m is not None:
    print(m.span(), m.group(), m.pos, m.endpos)
print([x.group() for x in re.compile(".").finditer("éé", 1, 3)], re.compile(".").fullmatch("éa", 1, 3))

# Bounds that used to split an astral UTF-8 sequence now refer to complete code points.
text = "a𝔄\n" + "z" * 30
for pos in [2, 3, 4]:
    m = re.compile("(?m)$").match(text, pos, 1)
    print("past endpos", pos, "None" if m is None else str(m.span()))
for end in [2, 3, 4]:
    m = re.compile("𝔄").match(text, 1, end)
    print("bounded end", end, "None" if m is None else str(m.span()))

inner = re.compile("b")


def mark(m) -> str:
    inner.search("xb")
    return "<" + str(m.group(1)) + str(m.start()) + ">"


print(re.compile("(é)").sub(mark, "aébé"), re.compile("(é)").subn(mark, "ééé"))
s = "aé日本😀b"
print([m.span() for m in re.finditer(".", s)])
rx = re.compile(".")
print([m.span() for m in rx.finditer(s, 2, 5)])
print([m.group() for m in rx.finditer(s, 2, 5)])
try:
    re.compile("é日本😀(")
except re.error as e:
    print(e.pos, e.lineno, e.colno)
