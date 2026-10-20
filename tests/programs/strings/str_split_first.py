# s.split(...)[0] is the first part alone, as CPython's list holds it: with a separator, the text
# before its first occurrence (all of s where there is none, or where maxsplit is 0); without one,
# the first word, and an IndexError where there is none. The receiver, the separator and maxsplit
# are evaluated in order before split raises, and any other receiver's split() is indexed as usual.


def show(label: str, v: str) -> None:
    print(label, repr(v))


def say(tag: str, v: str) -> str:
    print("evaluated", tag)
    return v


def count(n: int) -> int:
    print("evaluated maxsplit")
    return n


class Fields:
    def __init__(self, text: str) -> None:
        self.text = text

    def split(self, sep: str) -> list[str]:
        return ["fields", sep, self.text]

    def key(self) -> str:
        return self.text.split("=", 1)[0]


line = "http.request\t200\tGET /"
show("tab, 1", line.split("\t", 1)[0])
show("tab", line.split("\t")[0])
show("tab, -1", line.split("\t", -1)[0])
show("tab, 5", line.split("\t", 5)[0])
show("tab, 0", line.split("\t", 0)[0])
show("tab, True", line.split("\t", True)[0])
show("no tab", "http.request".split("\t", 1)[0])
show("at start", "\tx".split("\t", 1)[0])
show("at end", "x\t".split("\t", 1)[0])
show("empty", "".split(",", 1)[0])
show("long sep", "a<->b<->c".split("<->")[0])
show("sep longer than s", "ab".split("abc")[0])
show("sep is s", "abc".split("abc")[0])
show("non-ASCII", "é—ü—x".split("—", 1)[0])
show("non-ASCII sep", "aébéc".split("é")[0])

for s in ["  first second  ", "one", "\t\n x y", "a  b", "  a b ", "é ü"]:
    show(f"words {s!r}", s.split()[0])
    show(f"None {s!r}", s.split(None)[0])
    show(f"None, 0 {s!r}", s.split(None, 0)[0])
    show(f"None, 1 {s!r}", s.split(None, 1)[0])

for s in ["", "   ", "\t\n"]:
    try:
        print(s.split()[0])
    except IndexError as e:
        print("IndexError:", e, repr(s))
    try:
        print(s.split(None, 0)[0])
    except IndexError as e:
        print("IndexError:", e, repr(s))

for sep in ["", "x"]:
    try:
        show("sep " + repr(sep), "axb".split(sep)[0])
    except ValueError as e:
        print("ValueError:", e)
    try:
        show("sep " + repr(sep) + ", 0", "axb".split(sep, 0)[0])
    except ValueError as e:
        print("ValueError:", e)

maybe: list[str | None] = [None, ",", "-"]
for m in maybe:
    show(f"sep {m!r}", "a,b-c d".split(m)[0])
    show(f"sep {m!r}, 1", "a,b-c d".split(m, 1)[0])

# the order of evaluation, and what is evaluated before split raises
show("order", say("receiver", "k=v").split(say("sep", "="), count(1))[0])
try:
    say("receiver", "k=v").split(say("sep", ""), count(1))[0]
except ValueError as e:
    print("ValueError:", e)

# receivers of every kind
f = Fields("name=value=more")
words = ["a:b", "c:d"]
table = {"k": "x;y"}
show("attr", f.text.split("=")[0])
show("method", f.key())
show("call", "  key = v ".strip().split("=")[0])
show("index", words[1].split(":")[0])
show("dict", table["k"].split(";", 1)[0])
show("literal", "left|right".split("|")[0])
show("nested", "a.b,c".split("abc,.".split(",")[1])[0])
show("chained", "x/y/z".split("/", 1)[0].split("x")[0])
print([w.split(":")[0] for w in words], [w.split(":")[1] for w in words])
pairs: dict[str, str] = {}
for w in words:
    pairs[w.split(":")[0]] = w.split(":", 1)[-1]
print(pairs)
print("fields", f.split("=")[0], f.split("=")[1])  # (another class's split, indexed as usual)
print("rsplit", "a,b,c".rsplit(",", 1)[0], "a,b,c".split(",")[1], "a,b,c".split(",")[-1])

opt: str | None = None
for v in ["p q", None]:
    opt = v
    try:
        show("optional", opt.split()[0])
    except AttributeError as e:
        print("AttributeError:", e)
