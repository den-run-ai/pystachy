# Class runs and class scans decide ASCII characters by the Pattern's table, and code points from
# U+0080 by one range (or none, or all) when the class allows, else by its bytecode. Cover each
# kind with negation, categories, the U+007F/U+0080, U+00FF/U+0100 and astral boundaries, folding
# to ASCII, every repeat form, backtracking, empty matches and pos/endpos windows.
import re


def describe(m: re.Match | None) -> str:
    if m is None:
        return "None"
    return str(m.start()) + ":" + str(m.end()) + " " + repr(m.group(0))


def spans(rx: re.Pattern, text: str) -> str:
    return ",".join([str(m.start()) + ":" + str(m.end()) for m in rx.finditer(text)])


CLASSES = [
    r"[a-z_]",
    r"[^#?]",
    r"[^a-z]",
    r"(?a:\D)",
    r"(?a:[^\s\d])",
    r"(?a:[\d\u00e9])",
    r"(?a:[\D\u00e9])",
    r"(?a:[^\D])",
    r"[\x7f-\x80]",
    r"[a-z\u00e0-\u00ff]",
    r"[a-z\u00c0-\u00d6\u00d8-\u00f6]",
    r"[^\x80-\xff]",
    r"[\u00e9\u00ea]",
    r"[\u0400-\u04ff]",
    r"[^\u0400-\u04ff]",
    r"[\U00010000-\U0010ffff]",
    r"[^\U00010000-\U0010ffff]",
    r"[\x80-\U0010ffff]",
    r"[\u0100-\u0110\u0400-\u0410]",
    r"[a\u0100\u0200\u0300\u0400]",
    r"\w",
    r"[^\w\u0400]",
    r"(?i:[a-z])",
    r"(?ai:[a-z])",
    r"(?i:[^a-z])",
    r"(?i:[\u0400-\u04ff])",
    r"(?i:[k\u00e9])",
]
TEXTS = [
    "abc_XYZ#?az",
    "\x7f\x80\x81\xe0\xe9\xea\xf7\xff\u0100",
    "\u0400\u0401\u044f\u04ff\u0500\u0410a",
    "\U00010000\U0010ffff\uffff\U0001f600a",
    "K\u212a\u017fs\u0130i\u0131I\u00e9\u00c9",
    "12\u0661\u0662 \u00a0\t9\u00e9",
]
for c in CLASSES:
    print(c)
    for repeat in ["+", "*", "{2,3}", "{2,3}?", "++", "*?"]:
        rx = re.compile(c + repeat)
        print(" ", repeat, "|".join([spans(rx, t) for t in TEXTS]))

# Searches whose pattern begins with a class (INFO's charset) or with a repeated class
# (_repeated's first item), with a window that cuts the subject on both sides
for pattern in [r"[#?\u00e9]x", r"[^a-z]x", r"[\u0400-\u04ff]x", r"([a-z\u00e0-\u00ff]+)x",
                r"(?i:([\u0400-\u04ff]+))x", r"(?i:(k+))x", r"(?ai:(k+))x", r"(\w+)x",
                r"([^\U00010000-\U0010ffff]+)x", r"(?i:(\u00e9+))x"]:
    rx = re.compile(pattern)
    text = "--\u00e9x\u0410x\u212ax\U0001f600x kx\u00c9x Kx\u0430\u0410x--"
    print(pattern, describe(rx.search(text)), [describe(rx.search(text, p, e)) for p, e in
                                                [(0, 5), (3, 9), (4, 13), (9, 20), (12, 30)]])

# A greedy run gives back what its tail needs, and a lazy one takes what it must
for pattern in [r"([\u0400-\u04ff]+)\u044f", r"([^#?]*)\u00e9", r"([\x80-\U0010ffff]{1,4}?)\U0010ffff",
                r"((?i:[^a-z])+)K", r"([a-z\u00e0-\u00ff]++)\u00ff"]:
    rx = re.compile(pattern)
    for text in ["\u0410\u044f\u044f\u044f", "ab\u00e9cd\u00e9#\u00e9", "\x80\u0100\U0010ffff\U0010ffff",
                 "\u00e9\u212a12K", "abc\u00e0\u00ff"]:
        print(pattern, repr(text), describe(rx.search(text)))

# findall, sub and split over the same subject keep their spans in code points
rx = re.compile(r"[^\x00-\x7f]+")
text = "a\u00e9b\u0410\u0411c\U0001f600d\x7f\x80e"
print(rx.findall(text), rx.sub("<>", text), rx.split(text))
rx = re.compile(r"[\x00-\x7f]+")
print(rx.findall(text), rx.sub("<>", text), rx.split(text))
