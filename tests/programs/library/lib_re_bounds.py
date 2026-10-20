# Bounded matching retains the prefix for lookbehind/anchors, clamps both bounds, and stops
# at endpos even when a non-ASCII character or an otherwise matching suffix follows it.
import re


def show(m) -> str:
    return "None" if m is None else "%s:%r" % (m.span(), m.group())


subject = "ab\ncXYZ" * 20
for pattern in ["", ".", "^", "$", "(?m)^", "(?m)$", r"\b", r"\B", r"\Z", "(?<=ab)", "(?<=b)\\nc"]:
    rx = re.compile(pattern)
    for pos, end in [(0, 1), (1, 2), (2, 0), (3, 2), (3, 4), (-5, 1), (999, 999), (2, -1)]:
        print(pattern, pos, end, show(rx.match(subject, pos, end)), show(rx.search(subject, pos, end)),
              show(rx.fullmatch(subject, pos, end)))

for prefix in ["", "a", "é", "é☃𝔄"]:
    text = prefix + "é" + "☃𝔄" * 10
    pos = len(prefix)
    end = len(prefix + "é")
    rx = re.compile("(?<=" + prefix + ")é$")
    m = rx.match(text, pos, end)
    print("unicode", prefix, m is not None)
    if m is not None:
        print(m.group(), m.start() == pos, m.end() == end, m.pos == pos, m.endpos == end, m.string == text)
    print(rx.findall(text, pos, end), [x.group() for x in rx.finditer(text, pos, end)])


# A replacement callback can change the cache, grow that subject's bounded prefix, and purge it.
inner = re.compile(".")
other = "é☃𝔄" * 20


def replacement(m) -> str:
    inner.match(other, 0, len("é"))
    inner.match(other, 0, len(other))
    re.purge()
    return "<" + m.group() + ">"


print(re.sub("é", replacement, "aébécé"))
