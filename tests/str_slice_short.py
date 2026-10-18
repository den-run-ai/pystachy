# Empty and 1-byte slices, and the parts of split, rsplit, splitlines and partition that are
# empty or one character: appending to them, hashing them and keying a dict with them leave
# every other such str as it was (the runtime shares them, as CPython shares "" and ASCII chars).
# A str's index is a byte's (a documented deviation), so non-ASCII text is only split here


def show(xs: list[str]) -> None:
    print(len(xs), [x for x in xs], [len(x) for x in xs])


def main() -> None:
    s = "abc,,d,x,,"
    print(repr(s[0:0]), repr(s[5:5]), repr(s[9:3]), repr(s[100:]), repr(s[:-100]))
    print(repr(s[0:1]), repr(s[-1:]), repr(s[1:2]), repr(s[-4:-3]))
    print(repr(s[::-1][:1]), repr(s[2:3:5]), repr(s[3:0:-10]), repr(s[0:0:-1]), repr(s[::100]))
    e = ""
    print(repr(e[:]), repr(e[0:0]), repr(e[::-1]), len(e[1:]))

    parts = ("," * 20).split(",")
    show(parts)
    show("a,b,,c,".split(","))
    show("a,b,,c,".rsplit(","))
    show("a,b,,c,".split(",", 2))
    show(",x,".rsplit(",", 1))
    show("x\n\ny\r\nz\n".splitlines())
    show("x\n\ny\r\nz\n".splitlines(True))
    u8 = "é,ü,,ö,é".split(",")
    print(u8, "ü,".rsplit(","), "é\n\nü".splitlines(), "é=".partition("="), "=ü".rpartition("="))
    w = u8[0]
    w += u8[1]
    w += u8[2]
    print(w, u8, {p: i for i, p in enumerate(u8)}, hash(u8[0]) == hash("é"), hash(u8[2]) == hash(""))
    show(" a  b ".split(" "))
    show(" a  b ".split())
    print("a=".partition("="), "=b".rpartition("="), "x".partition("x"), "".partition(","))

    # appending to an empty or 1-char part: the others stay as they were
    acc = parts[0]
    for i in range(5):
        acc += "z"
    one = "q,q,q".split(",")
    first = one[0]
    for i in range(3):
        first += str(i)
    print(repr(acc), repr(parts[1]), repr(parts[2]), first, one)
    t = s[1:2]
    t += t
    t += s[1:2]
    print(t, s[1:2], s[1:2] + s[1:2], s)
    u = s[4:4]
    u += "x"
    u += "y"
    print(u, repr(s[4:4]), len(s[4:4]), repr(e[:]))

    # hashes and dict keys: the same as those of any equal str
    print(hash(s[0:0]) == hash(""), hash(s[0:1]) == hash("a"), hash(s[6:7]) == hash(","))
    d: dict[str, int] = {}
    for p in "a,b,,a,,c,b,".split(","):
        d[p] = d.get(p, 0) + 1
    print(sorted(d.items()))
    print(d[""], d["a"], d.get(s[0:1], -1), d.get(s[3:3], -1), "" in d, s[1:2] in d)
    k: dict[str, str] = {s[0:0]: "empty", s[0:1]: "a", "b": "b", s[5:6]: "d"}
    print(sorted(k.items()), k[""], k["a"], k[s[2:3]] if s[2:3] in k else "no c")
    seen: set[str] = set()
    for c in "hello, world".split("l"):
        seen.add(c)
    print(sorted(seen))
    print([x + "!" for x in "a,,b".split(",")], "a,,b".split(","))


main()
