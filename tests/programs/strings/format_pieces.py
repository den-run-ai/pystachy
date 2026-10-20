# f-strings, % formats and the repr of dataclasses and NamedTuples with many pieces, which are
# joined at once (two pieces by +, up to eight in one copy, more eight by eight): the pieces' order
# across those boundaries, the order in which fields, conversions, nested format specs and user
# __format__/__str__/__repr__ run, a raise part of the way through, and non-ASCII and long pieces
from dataclasses import dataclass
from typing import NamedTuple

xs = [chr(97 + i % 26) * (i % 3 + 1) + str(i) for i in range(131)]

print(2, f"{xs[0]}{xs[1]}")
print(3, f"{xs[0]}{xs[1]}{xs[2]}")
print(4, f"{xs[0]}{xs[1]}{xs[2]}{xs[3]}")
print(7, f"{xs[0]}{xs[1]}{xs[2]}{xs[3]}{xs[4]}{xs[5]}{xs[6]}")
print(8, f"{xs[0]}{xs[1]}{xs[2]}{xs[3]}{xs[4]}{xs[5]}{xs[6]}{xs[7]}")
print(9, f"{xs[0]}{xs[1]}{xs[2]}{xs[3]}{xs[4]}{xs[5]}{xs[6]}{xs[7]}{xs[8]}")
print(16, f"{xs[0]}{xs[1]}{xs[2]}{xs[3]}{xs[4]}{xs[5]}{xs[6]}{xs[7]}{xs[8]}{xs[9]}{xs[10]}{xs[11]}{xs[12]}{xs[13]}{xs[14]}{xs[15]}")
print(17, f"{xs[0]}{xs[1]}{xs[2]}{xs[3]}{xs[4]}{xs[5]}{xs[6]}{xs[7]}{xs[8]}{xs[9]}{xs[10]}{xs[11]}{xs[12]}{xs[13]}{xs[14]}{xs[15]}{xs[16]}")
print(63, f"{xs[0]}{xs[1]}{xs[2]}{xs[3]}{xs[4]}{xs[5]}{xs[6]}{xs[7]}{xs[8]}{xs[9]}{xs[10]}{xs[11]}{xs[12]}{xs[13]}{xs[14]}{xs[15]}{xs[16]}{xs[17]}{xs[18]}{xs[19]}{xs[20]}{xs[21]}{xs[22]}{xs[23]}{xs[24]}{xs[25]}{xs[26]}{xs[27]}{xs[28]}{xs[29]}{xs[30]}{xs[31]}{xs[32]}{xs[33]}{xs[34]}{xs[35]}{xs[36]}{xs[37]}{xs[38]}{xs[39]}{xs[40]}{xs[41]}{xs[42]}{xs[43]}{xs[44]}{xs[45]}{xs[46]}{xs[47]}{xs[48]}{xs[49]}{xs[50]}{xs[51]}{xs[52]}{xs[53]}{xs[54]}{xs[55]}{xs[56]}{xs[57]}{xs[58]}{xs[59]}{xs[60]}{xs[61]}{xs[62]}")
print(64, f"{xs[0]}{xs[1]}{xs[2]}{xs[3]}{xs[4]}{xs[5]}{xs[6]}{xs[7]}{xs[8]}{xs[9]}{xs[10]}{xs[11]}{xs[12]}{xs[13]}{xs[14]}{xs[15]}{xs[16]}{xs[17]}{xs[18]}{xs[19]}{xs[20]}{xs[21]}{xs[22]}{xs[23]}{xs[24]}{xs[25]}{xs[26]}{xs[27]}{xs[28]}{xs[29]}{xs[30]}{xs[31]}{xs[32]}{xs[33]}{xs[34]}{xs[35]}{xs[36]}{xs[37]}{xs[38]}{xs[39]}{xs[40]}{xs[41]}{xs[42]}{xs[43]}{xs[44]}{xs[45]}{xs[46]}{xs[47]}{xs[48]}{xs[49]}{xs[50]}{xs[51]}{xs[52]}{xs[53]}{xs[54]}{xs[55]}{xs[56]}{xs[57]}{xs[58]}{xs[59]}{xs[60]}{xs[61]}{xs[62]}{xs[63]}")
print(65, f"{xs[0]}{xs[1]}{xs[2]}{xs[3]}{xs[4]}{xs[5]}{xs[6]}{xs[7]}{xs[8]}{xs[9]}{xs[10]}{xs[11]}{xs[12]}{xs[13]}{xs[14]}{xs[15]}{xs[16]}{xs[17]}{xs[18]}{xs[19]}{xs[20]}{xs[21]}{xs[22]}{xs[23]}{xs[24]}{xs[25]}{xs[26]}{xs[27]}{xs[28]}{xs[29]}{xs[30]}{xs[31]}{xs[32]}{xs[33]}{xs[34]}{xs[35]}{xs[36]}{xs[37]}{xs[38]}{xs[39]}{xs[40]}{xs[41]}{xs[42]}{xs[43]}{xs[44]}{xs[45]}{xs[46]}{xs[47]}{xs[48]}{xs[49]}{xs[50]}{xs[51]}{xs[52]}{xs[53]}{xs[54]}{xs[55]}{xs[56]}{xs[57]}{xs[58]}{xs[59]}{xs[60]}{xs[61]}{xs[62]}{xs[63]}{xs[64]}")
print(66, f"{xs[0]}{xs[1]}{xs[2]}{xs[3]}{xs[4]}{xs[5]}{xs[6]}{xs[7]}{xs[8]}{xs[9]}{xs[10]}{xs[11]}{xs[12]}{xs[13]}{xs[14]}{xs[15]}{xs[16]}{xs[17]}{xs[18]}{xs[19]}{xs[20]}{xs[21]}{xs[22]}{xs[23]}{xs[24]}{xs[25]}{xs[26]}{xs[27]}{xs[28]}{xs[29]}{xs[30]}{xs[31]}{xs[32]}{xs[33]}{xs[34]}{xs[35]}{xs[36]}{xs[37]}{xs[38]}{xs[39]}{xs[40]}{xs[41]}{xs[42]}{xs[43]}{xs[44]}{xs[45]}{xs[46]}{xs[47]}{xs[48]}{xs[49]}{xs[50]}{xs[51]}{xs[52]}{xs[53]}{xs[54]}{xs[55]}{xs[56]}{xs[57]}{xs[58]}{xs[59]}{xs[60]}{xs[61]}{xs[62]}{xs[63]}{xs[64]}{xs[65]}")
print(130, f"{xs[0]}{xs[1]}{xs[2]}{xs[3]}{xs[4]}{xs[5]}{xs[6]}{xs[7]}{xs[8]}{xs[9]}{xs[10]}{xs[11]}{xs[12]}{xs[13]}{xs[14]}{xs[15]}{xs[16]}{xs[17]}{xs[18]}{xs[19]}{xs[20]}{xs[21]}{xs[22]}{xs[23]}{xs[24]}{xs[25]}{xs[26]}{xs[27]}{xs[28]}{xs[29]}{xs[30]}{xs[31]}{xs[32]}{xs[33]}{xs[34]}{xs[35]}{xs[36]}{xs[37]}{xs[38]}{xs[39]}{xs[40]}{xs[41]}{xs[42]}{xs[43]}{xs[44]}{xs[45]}{xs[46]}{xs[47]}{xs[48]}{xs[49]}{xs[50]}{xs[51]}{xs[52]}{xs[53]}{xs[54]}{xs[55]}{xs[56]}{xs[57]}{xs[58]}{xs[59]}{xs[60]}{xs[61]}{xs[62]}{xs[63]}{xs[64]}{xs[65]}{xs[66]}{xs[67]}{xs[68]}{xs[69]}{xs[70]}{xs[71]}{xs[72]}{xs[73]}{xs[74]}{xs[75]}{xs[76]}{xs[77]}{xs[78]}{xs[79]}{xs[80]}{xs[81]}{xs[82]}{xs[83]}{xs[84]}{xs[85]}{xs[86]}{xs[87]}{xs[88]}{xs[89]}{xs[90]}{xs[91]}{xs[92]}{xs[93]}{xs[94]}{xs[95]}{xs[96]}{xs[97]}{xs[98]}{xs[99]}{xs[100]}{xs[101]}{xs[102]}{xs[103]}{xs[104]}{xs[105]}{xs[106]}{xs[107]}{xs[108]}{xs[109]}{xs[110]}{xs[111]}{xs[112]}{xs[113]}{xs[114]}{xs[115]}{xs[116]}{xs[117]}{xs[118]}{xs[119]}{xs[120]}{xs[121]}{xs[122]}{xs[123]}{xs[124]}{xs[125]}{xs[126]}{xs[127]}{xs[128]}{xs[129]}")

print(2, f"<{xs[0]}|{xs[1]}>")
print(4, f"<{xs[0]}|{xs[1]}|{xs[2]}|{xs[3]}>")
print(5, f"<{xs[0]}|{xs[1]}|{xs[2]}|{xs[3]}|{xs[4]}>")
print(32, f"<{xs[0]}|{xs[1]}|{xs[2]}|{xs[3]}|{xs[4]}|{xs[5]}|{xs[6]}|{xs[7]}|{xs[8]}|{xs[9]}|{xs[10]}|{xs[11]}|{xs[12]}|{xs[13]}|{xs[14]}|{xs[15]}|{xs[16]}|{xs[17]}|{xs[18]}|{xs[19]}|{xs[20]}|{xs[21]}|{xs[22]}|{xs[23]}|{xs[24]}|{xs[25]}|{xs[26]}|{xs[27]}|{xs[28]}|{xs[29]}|{xs[30]}|{xs[31]}>")
print(33, f"<{xs[0]}|{xs[1]}|{xs[2]}|{xs[3]}|{xs[4]}|{xs[5]}|{xs[6]}|{xs[7]}|{xs[8]}|{xs[9]}|{xs[10]}|{xs[11]}|{xs[12]}|{xs[13]}|{xs[14]}|{xs[15]}|{xs[16]}|{xs[17]}|{xs[18]}|{xs[19]}|{xs[20]}|{xs[21]}|{xs[22]}|{xs[23]}|{xs[24]}|{xs[25]}|{xs[26]}|{xs[27]}|{xs[28]}|{xs[29]}|{xs[30]}|{xs[31]}|{xs[32]}>")
print(65, f"<{xs[0]}|{xs[1]}|{xs[2]}|{xs[3]}|{xs[4]}|{xs[5]}|{xs[6]}|{xs[7]}|{xs[8]}|{xs[9]}|{xs[10]}|{xs[11]}|{xs[12]}|{xs[13]}|{xs[14]}|{xs[15]}|{xs[16]}|{xs[17]}|{xs[18]}|{xs[19]}|{xs[20]}|{xs[21]}|{xs[22]}|{xs[23]}|{xs[24]}|{xs[25]}|{xs[26]}|{xs[27]}|{xs[28]}|{xs[29]}|{xs[30]}|{xs[31]}|{xs[32]}|{xs[33]}|{xs[34]}|{xs[35]}|{xs[36]}|{xs[37]}|{xs[38]}|{xs[39]}|{xs[40]}|{xs[41]}|{xs[42]}|{xs[43]}|{xs[44]}|{xs[45]}|{xs[46]}|{xs[47]}|{xs[48]}|{xs[49]}|{xs[50]}|{xs[51]}|{xs[52]}|{xs[53]}|{xs[54]}|{xs[55]}|{xs[56]}|{xs[57]}|{xs[58]}|{xs[59]}|{xs[60]}|{xs[61]}|{xs[62]}|{xs[63]}|{xs[64]}>")
print(f"{xs[0]}{xs[1]}{xs[2]}{xs[3]}{xs[4]}{xs[5]}{xs[6]}{xs[7]}{xs[8]}{xs[9]}{xs[10]}{xs[11]}{xs[12]}{xs[13]}{xs[14]}{xs[15]}{xs[16]}{xs[17]}{xs[18]}{xs[19]}{xs[20]}{xs[21]}{xs[22]}{xs[23]}{xs[24]}{xs[25]}{xs[26]}{xs[27]}{xs[28]}{xs[29]}{xs[30]}{xs[31]}{xs[32]}{xs[33]}{xs[34]}{xs[35]}{xs[36]}{xs[37]}{xs[38]}{xs[39]}{xs[40]}{xs[41]}{xs[42]}{xs[43]}{xs[44]}{xs[45]}{xs[46]}{xs[47]}{xs[48]}{xs[49]}{xs[50]}{xs[51]}{xs[52]}{xs[53]}{xs[54]}{xs[55]}{xs[56]}{xs[57]}{xs[58]}{xs[59]}{xs[60]}{xs[61]}{xs[62]}{xs[63]}{xs[64]}" == "".join(xs[:65]), f"{xs[0]}, {xs[1]}, {xs[2]}, {xs[3]}, {xs[4]}, {xs[5]}, {xs[6]}, {xs[7]}, {xs[8]}, {xs[9]}, {xs[10]}, {xs[11]}, {xs[12]}, {xs[13]}, {xs[14]}, {xs[15]}, {xs[16]}, {xs[17]}, {xs[18]}, {xs[19]}, {xs[20]}, {xs[21]}, {xs[22]}, {xs[23]}, {xs[24]}, {xs[25]}, {xs[26]}, {xs[27]}, {xs[28]}, {xs[29]}, {xs[30]}, {xs[31]}, {xs[32]}, {xs[33]}, {xs[34]}, {xs[35]}, {xs[36]}, {xs[37]}, {xs[38]}, {xs[39]}, {xs[40]}, {xs[41]}, {xs[42]}, {xs[43]}, {xs[44]}, {xs[45]}, {xs[46]}, {xs[47]}, {xs[48]}, {xs[49]}, {xs[50]}, {xs[51]}, {xs[52]}, {xs[53]}, {xs[54]}, {xs[55]}, {xs[56]}, {xs[57]}, {xs[58]}, {xs[59]}, {xs[60]}, {xs[61]}, {xs[62]}, {xs[63]}, {xs[64]}" == ", ".join(xs[:65]))
print(f"{xs[100]}{xs[101]}{xs[102]}{xs[103]}{xs[104]}{xs[105]}{xs[106]}{xs[107]}{xs[108]}")

# a field that raises after many others: the pieces made before it are dropped
try:
    s = f"{xs[0]}{xs[1]}{xs[2]}{xs[3]}{xs[4]}{xs[5]}{xs[6]}{xs[7]}{xs[8]}{xs[9]}{xs[10]}{xs[11]}{xs[12]}{xs[13]}{xs[14]}{xs[15]}{xs[16]}{xs[17]}{xs[18]}{xs[19]}{xs[20]}{xs[21]}{xs[22]}{xs[23]}{xs[24]}{xs[25]}{xs[26]}{xs[27]}{xs[28]}{xs[29]}{xs[30]}{xs[31]}{xs[32]}{xs[33]}{xs[34]}{xs[35]}{xs[36]}{xs[37]}{xs[38]}{xs[39]}{xs[40]}{xs[41]}{xs[42]}{xs[43]}{xs[44]}{xs[45]}{xs[46]}{xs[47]}{xs[48]}{xs[49]}{xs[50]}{xs[51]}{xs[52]}{xs[53]}{xs[54]}{xs[55]}{xs[56]}{xs[57]}{xs[58]}{xs[59]}{xs[60]}{xs[61]}{xs[62]}{xs[63]}{xs[64]}{xs[65]}{xs[66]}{xs[67]}{xs[68]}{xs[69]}{xs[70]}{xs[71]}{xs[72]}{xs[73]}{xs[74]}{xs[75]}{xs[76]}{xs[77]}{xs[78]}{xs[79]}{xs[80]}{xs[81]}{xs[82]}{xs[83]}{xs[84]}{xs[85]}{xs[86]}{xs[87]}{xs[88]}{xs[89]}{xs[90]}{xs[91]}{xs[92]}{xs[93]}{xs[94]}{xs[95]}{xs[96]}{xs[97]}{xs[98]}{xs[99]}{xs[100]}{xs[101]}{xs[102]}{xs[103]}{xs[104]}{xs[105]}{xs[106]}{xs[107]}{xs[108]}{xs[109]}{xs[110]}{xs[111]}{xs[112]}{xs[113]}{xs[114]}{xs[115]}{xs[116]}{xs[117]}{xs[118]}{xs[119]}{xs[120]}{xs[121]}{xs[122]}{xs[123]}{xs[124]}{xs[125]}{xs[126]}{xs[127]}{xs[128]}{xs[129]}{xs[130]}{xs[131]}"
    print("not reached", s)
except IndexError as e:
    print("IndexError", e)

# what each piece's evaluation does, in order: CPython evaluates a field's expression, then its
# conversion, then its format spec (an f-string itself), then formats
log: list[str] = []


class T:
    def __init__(self, name: str) -> None:
        self.name = name
        log.append("new " + name)

    def __format__(self, spec: str) -> str:
        log.append(f"format {self.name} {spec!r}")
        if spec == "boom":
            raise ValueError("boom in " + self.name)
        return f"[{self.name}:{spec}]"

    def __str__(self) -> str:
        log.append("str " + self.name)
        if self.name == "bad":
            raise KeyError(self.name)
        return f"<{self.name}>"

    def __repr__(self) -> str:
        log.append("repr " + self.name)
        return f"T({self.name!r})"


def sp(s: str) -> str:
    log.append("spec " + s)
    return s


def show(what: str) -> None:
    print(what, "|", " ; ".join(log))
    log.clear()


show(f"a{T('a')}b{T('b')!r:>{sp('9')}}c{T('c')!s:{sp('^')}{sp('7')}}d{T('d'):{sp('x')}{sp('y')}}e{T('é')!a}f")
show(f"{T('g')}{T('h')}{T('i')!s}{T('j')!r}{T('k')}{T('l'):{sp('<')}}{T('m')}{T('n')}{T('o')}{T('p')}")
try:
    s = f"{T('q')}-{T('r')!r}-{T('s'):{sp('bo')}{sp('om')}}-{T('t')}-{T('u')}-{T('v')}-{T('w')}-{T('x')}-{T('y')}"
    print("not reached", s)
except ValueError as e:
    show("ValueError " + str(e))
try:
    s = f"{T('z')}{sp('.')}{T('bad')!s}{T('zz')}"
    print("not reached", s)
except KeyError as e:
    show("KeyError " + str(e))
# (made first: CPython 3.13 evaluates the items of a tuple of only %s, %r and %a in turn with
# their conversions, Pystachy all of them first)
ms = [T("m1"), T("m2"), T("m3"), T("m4"), T("bad"), T("m6"), T("m7"), T("m8"), T("m9"), T("p1"), T("p2"), T("p3"), T("ü")]
show("made")
try:
    s = "%s %r %s %s %s %s %s %s %s" % (ms[0], ms[1], ms[2], ms[3], ms[4], ms[5], ms[6], ms[7], ms[8])
    print("not reached", s)
except KeyError as e:
    show("KeyError " + str(e))
show("%s|%r|%5s|%-6s|%a|%d" % (ms[9], ms[10], "ab", ms[11], ms[12], len(log)))

# % with many conversions, a tuple held in a variable, one value, a NamedTuple and a dict
ws = ["w" + str(i) * 2 for i in range(10)]
for i in range(3):
    print("%d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %s %s %s %s %s %s %s %s %s %s %r %r %r %r %r %5.1f %5.1f %5.1f %5.1f %5.1f %x %o %c %% %+d %05d %-4d|" % (i + 0, i + 1, i + 2, i + 3, i + 4, i + 5, i + 6, i + 7, i + 8, i + 9, i + 10, i + 11, i + 12, i + 13, i + 14, i + 15, i + 16, i + 17, i + 18, i + 19, ws[0], ws[1], ws[2], ws[3], ws[4], ws[5], ws[6], ws[7], ws[8], ws[9], ws[0], ws[1], ws[2], ws[3], ws[4], i / 1, i / 2, i / 3, i / 4, i / 5, 255 + i, 8 + i, 65 + i, i, i * 3, i - 1))
t = (7, "seven", 7.5)
print("%d=%s (%.2f)" % t, "%s" % "one", "%5s|%-5s|" % ("ab", "cd"), "%s%s%s" % ("", "", ""))


class P(NamedTuple):
    x: int
    y: str
    z: float


print("%d/%s/%s/%r" % (P(3, "three", 0.5).x, P(3, "three", 0.5).y, P(3, "three", 0.5), P(3, "three", 0.5)))
print("%d/%s/%s" % P(4, "four", 1.5))
d = {"k": 1, "é": 2}
print("%s" % d, "%r|%s|%s" % (d, d, [d]))

# non-ASCII pieces, also as fill characters and in widths
u = "ünï"
print(f"{u}·{u!r}·{u!a}·{u:*^9}·{'日本語'}·{'😀':>3}·{u}{u}{u}{u}{u}{u}{u}{u}{u}·")
print("%s·%r·%a·%-6s|%6s|" % (u, u, u, "é", "日本"))

# adjacent literals, = fields, empty pieces, bools, None, and f-strings in fields and specs
x = 5
y = "why"
e = ""
flag = True
ns: str | None = None
print("lit" f"{x}" "a" "b" f"{y=}" "" f"{x=:>4}" f"{y!r:>8}" "end")
print(f"{e}{e}{x}{e}{e}|", f"{e}{e}{e}|", f"{''}{e}{''}|", f"{e}{e}{e}{e}{e}{e}{e}{e}{e}{e}|")
print(f"{flag}{ns}{x}{not flag}{ns!r}{x}{flag!r}{ns}{None}{x}")
a, b, c = "A", "B", "C"
print(f"{f'{a}{b}{c}'}{f'{c}-{b}-{a}':>9}{a}{b}{c}{a}{b}{c}{a}")
wd = 12
pr = 3
print(f"[{3.14159265:{'<'}{wd}{'.'}{pr}{'f'}}]", f"[{'x':{'*'}{'^'}{wd}}]", f"[{x:{'+'}{wd - 4}{'d'}}|{y:{'>'}{wd}}]")
print(f"{[1, 2]}{(3, 'x')}{ {'a': 1} }{[y, 'z']!r}{(x,)}")

# long pieces: one copy of each
big = [chr(65 + i % 26) * 1000 for i in range(70)]
s = f"{big[0]}{big[1]}{big[2]}{big[3]}{big[4]}{big[5]}{big[6]}{big[7]}{big[8]}{big[9]}{big[10]}{big[11]}{big[12]}{big[13]}{big[14]}{big[15]}{big[16]}{big[17]}{big[18]}{big[19]}{big[20]}{big[21]}{big[22]}{big[23]}{big[24]}{big[25]}{big[26]}{big[27]}{big[28]}{big[29]}{big[30]}{big[31]}{big[32]}{big[33]}{big[34]}{big[35]}{big[36]}{big[37]}{big[38]}{big[39]}{big[40]}{big[41]}{big[42]}{big[43]}{big[44]}{big[45]}{big[46]}{big[47]}{big[48]}{big[49]}{big[50]}{big[51]}{big[52]}{big[53]}{big[54]}{big[55]}{big[56]}{big[57]}{big[58]}{big[59]}{big[60]}{big[61]}{big[62]}{big[63]}{big[64]}{big[65]}{big[66]}{big[67]}{big[68]}{big[69]}"
print(len(s), s == "".join(big), s[995:1005], s[-1005:-995])
s = f"{big[0]}{x}{big[1]}{y}{big[2]}"
print(len(s), s[995:1010])

# many f-strings in a loop (collections run while pieces wait to be joined)
acc = 0
for i in range(3000):
    s = f"{i}:{xs[i % 131]}|{i * 2}|{xs[(i * 7) % 131]}|{i % 3 == 0}|{-i}|{i / 4}|{xs[i % 13]}!"
    t2 = "%d-%s-%d" % (i, xs[i % 131], i * 3)
    acc += len(s) + ord(s[len(s) // 2]) + len(t2)
print(acc)


# dataclass and NamedTuple reprs: two pieces per field
@dataclass
class Inner:
    name: str
    vals: list[int]


@dataclass
class Mixed:
    a: int
    b: str
    c: float
    d: list[str]
    e: Inner
    f: str | None
    g: bool
    h: tuple[int, str]
    i: dict[str, int]
    j: str


m = Mixed(1, "it's", 2.5, ["x", 'y"'], Inner("in", [1, 2]), None, True, (3, "t"), {"k": 4}, "é")
print(m)
print(repr(m) == str(m), repr(m) == f"{m}", repr(m) == f"{m!r}")


@dataclass
class D70:
    f0: int
    f1: int
    f2: int
    f3: int
    f4: int
    f5: int
    f6: int
    f7: int
    f8: int
    f9: int
    f10: int
    f11: int
    f12: int
    f13: int
    f14: int
    f15: int
    f16: int
    f17: int
    f18: int
    f19: int
    f20: int
    f21: int
    f22: int
    f23: int
    f24: int
    f25: int
    f26: int
    f27: int
    f28: int
    f29: int
    f30: int
    f31: int
    f32: int
    f33: int
    f34: int
    f35: int
    f36: int
    f37: int
    f38: int
    f39: int
    f40: int
    f41: int
    f42: int
    f43: int
    f44: int
    f45: int
    f46: int
    f47: int
    f48: int
    f49: int
    f50: int
    f51: int
    f52: int
    f53: int
    f54: int
    f55: int
    f56: int
    f57: int
    f58: int
    f59: int
    f60: int
    f61: int
    f62: int
    f63: int
    f64: int
    f65: int
    f66: int
    f67: int
    f68: int
    f69: int


print(D70(0, 7, 14, 21, 28, 35, 42, 49, 56, 63, 70, 77, 84, 91, 98, 105, 112, 119, 126, 133, 140, 147, 154, 161, 168, 175, 182, 189, 196, 203, 210, 217, 224, 231, 238, 245, 252, 259, 266, 273, 280, 287, 294, 301, 308, 315, 322, 329, 336, 343, 350, 357, 364, 371, 378, 385, 392, 399, 406, 413, 420, 427, 434, 441, 448, 455, 462, 469, 476, 483))


class N12(NamedTuple):
    a: int
    b: str
    c: float
    d: int
    e: str
    f: bool
    g: int
    h: str
    i: int
    j: str
    k: int
    l: str


print(N12(1, "b", 3.0, 4, "e", False, 7, "h", 9, "j", 11, "l"))


class Flaky:
    def __init__(self) -> None:
        self.n = 0

    def __repr__(self) -> str:
        self.n += 1
        if self.n == 1:
            raise RuntimeError("flaky")
        return "Flaky(" + str(self.n) + ")"


@dataclass
class Holder:
    a: int
    b: Flaky
    c: str
    d: int
    e: str


h = Holder(1, Flaky(), "c", 4, "e")
try:
    print(h)
except RuntimeError as err:
    print("RuntimeError", err)
print(h)
print(repr(h))
