# lib/csv: Pystachy's csv, after CPython 3.13's Modules/_csv.c and Lib/csv.py; each result is
# compared with CPython's own csv (cases from CPython's Lib/test/test_csv.py, then random ones)
import csv
import os
import sys
import tempfile


class Sink:
    # an object of the program's with a write() method, which a writer writes its lines to
    def __init__(self) -> None:
        self.parts: list[str] = []

    def write(self, s: str) -> int:
        self.parts.append(s)
        return len(self.parts)


def rd(lines: list[str], delimiter: str = ",", quotechar: str | None = '"', escapechar: str | None = None,
       doublequote: bool = True, skipinitialspace: bool = False, strict: bool = False,
       quoting: int = csv.QUOTE_MINIMAL) -> None:
    # the rows of lines, or the error, and line_num
    try:
        r = csv.reader(lines, delimiter=delimiter, quotechar=quotechar, escapechar=escapechar,
                       doublequote=doublequote, skipinitialspace=skipinitialspace, strict=strict,
                       quoting=quoting)
        rows = list(r)
        print(rows, r.line_num)
    except csv.Error as e:
        print("Error:", e)
    except (TypeError, ValueError) as e:
        print(type(e).__name__ + ":", e)


def wr(row, delimiter: str = ",", quotechar: str | None = '"', escapechar: str | None = None,
       doublequote: bool = True, skipinitialspace: bool = False, lineterminator: str = "\r\n",
       quoting: int = csv.QUOTE_MINIMAL) -> None:
    # the line writerow() writes of row, or the error
    out = Sink()
    try:
        w = csv.writer(out, delimiter=delimiter, quotechar=quotechar, escapechar=escapechar,
                       doublequote=doublequote, skipinitialspace=skipinitialspace,
                       lineterminator=lineterminator, quoting=quoting)
        w.writerow(row)
        print(repr("".join(out.parts)))
    except csv.Error as e:
        print("Error:", e, out.parts)
    except (TypeError, ValueError) as e:
        print(type(e).__name__ + ":", e)


print("-- reading: line ends")
rd(["a,b", "c,d"])
rd(["a,b\n", "c,d\n"])
rd(["a,b\r\n", "c,d\r\n"])
rd(["a,b\r", "c,d\r"])
rd(["a,b\rc,d"])
rd(["a,b\nc,d"])
rd(["a,b\r\nc,d"])
rd([""])
rd(["", "", "x"])
rd(["\n", "\r\n", "\r"])
noline: list[str] = []
rd(noline)

print("-- reading: odd inputs, the end of the data")
rd(['"ab"c'], strict=True)
rd(['"ab"c'], doublequote=False)
rd(['a,"'])
rd(['"a'])
rd(["^"], escapechar="^")
rd(['a,"'], strict=True)
rd(['"a'], strict=True)
rd(["^"], escapechar="^", strict=True)
rd(["a,b\\"], escapechar="\\")
rd(["a,b\\", "c"], escapechar="\\")
rd(["a\\\rb", "c", "d\n"], escapechar="\\")
rd(['"a\\', 'b"'], escapechar="\\")

print("-- reading: NUL")
rd(["\0"])
rd(["a,\0b,c"])
rd(["a,b\0,c"])
rd(["a,b\\\0,c"], escapechar="\\")
rd(['a,"\0b",c'])
rd(["a\0b\0c"], delimiter="\0")

print("-- reading: escapechar")
rd(["a,\\b,c"], escapechar="\\")
rd(["a,b\\,c"], escapechar="\\")
rd(['a,"b\\,c"'], escapechar="\\")
rd(['a,"b,\\c"'], escapechar="\\")
rd(['a,"b,c\\""'], escapechar="\\")
rd(['a,"b,c"\\'], escapechar="\\")
rd(["a,^b,c"], escapechar="^")
rd(["a,\0b,c"], escapechar="\0")
rd(["a,\\b,c"], escapechar=None)
rd(["a,\\b,c"])
rd(["abc\\,def\r\n"], escapechar="\\", quoting=csv.QUOTE_NONE)
rd(['"abc\\,def"\r\n'], escapechar="\\")

print("-- reading: quoting")
rd(['1,",3,",5'])
rd(['1,",3,",5'], quotechar=None, escapechar="\\", quoting=csv.QUOTE_NONE)
rd(['1,",3,",5'], quoting=csv.QUOTE_NONE, escapechar="\\")
rd([',,"",'])
rd(['"a\nb", 7'])
rd(["1,@,3,@,5"], quotechar="@")
rd(["1,\0,3,\0,5"], quotechar="\0")
rd(['"1","abc def","abc"\n'], quoting=csv.QUOTE_ALL)
rd(['a""b', 'a"b"c', '"a"b', 'a"b', '"a" "b"', ' "a"'])
rd(['""', '"",', ',""', '""""', '""""""'])
rd(['12,12,1",'])
rd(['1,2,3,"I think, therefore I am",5,6'])
rd(['1,2,3,"""I see,"" said the blind man","as he picked up his hammer and saw"'])
rd(['1,2,3,"""I see,""\n', 'said the blind man","as he picked up his\n', 'hammer and saw"\n', "9,8,7,6"])
rd(['"a"b,c', '"a"""b"'], strict=True)
rd(['"a" ,b'], strict=True)
rd(['"a"\n'], strict=True)
rd(['"a"x'], strict=True, delimiter=";")
rd(["'a''b',c"], quotechar="'")

print("-- reading: skipinitialspace and spaces")
rd(["no space, space,  spaces,\ttab"], skipinitialspace=True)
rd([" , , "], skipinitialspace=True)
rd(["a   b", "  a  ", "  ", ""], delimiter=" ")
rd(["a   b", "  a  ", "  ", ""], delimiter=" ", skipinitialspace=True)
rd(['a, "b,c", d'], skipinitialspace=True)
rd(["abc   def\n", "c1ccccc1 benzene\n"], delimiter=" ", quoting=csv.QUOTE_NONE, escapechar="\\")

print("-- reading: iteration, line_num, dialect")
r = csv.reader(["line,1", "line,2", "line,3"])
print(r.line_num, r.dialect.delimiter, r.dialect is csv.get_dialect("excel"))
for row in r:
    print(row)
print(r.line_num, list(r), r.line_num)
r = csv.reader(["a,b\n", '"multi\n', 'line",x\n', "\n", "z"])
print(list(r), r.line_num)
print([row for row in csv.reader(("x;y", "1;2"), delimiter=";")])
print(sorted(csv.reader(["b,1", "a,2", "c,0"])))
for i, row in enumerate(csv.reader(["p,q", "r,s"]), 1):
    print(i, row)
print(csv.reader(["a"], "excel-tab").dialect.delimiter == "\t", csv.reader(["a"], csv.unix_dialect).dialect.lineterminator == "\n")
print(list(csv.reader(["a\tb\tc"], dialect="excel-tab")), list(csv.reader(["a\tb"], csv.excel_tab)))
print(list(csv.reader(['"1","2"'], dialect="unix")))

print("-- reading: errors")
rd(["a,b", '"c'], strict=True)
rd(["a,b", "c\nd"])
rd(['"x"y'], strict=True)
rd(["a,", ' "b"x'], strict=True, skipinitialspace=True)
try:
    list(csv.reader(["a"], "nonesuch"))
except csv.Error as e:
    print("Error:", e, repr(e))
try:
    csv.reader(["a"], foo=1)
except TypeError as e:
    print("TypeError:", e)
try:
    list(csv.reader([1, 2]))
except csv.Error as e:
    print("Error:", e)

print("-- writing: quoting")
wr(("a", 1, "p,q"))
wr(("a", 1, "p,q"), quoting=csv.QUOTE_NONE)
wr(("a", 1, "p,q"), quoting=csv.QUOTE_MINIMAL)
wr(("a", 1, "p,q"), quoting=csv.QUOTE_NONNUMERIC)
wr(("a", 1, "p,q"), quoting=csv.QUOTE_ALL)
wr(("a\nb", 1), quoting=csv.QUOTE_ALL)
wr(("a", "", None, 1), quoting=csv.QUOTE_STRINGS)
wr(("a", "", None, 1), quoting=csv.QUOTE_NOTNULL)
wr(("a", "", None, 1, 2.5, True), quoting=csv.QUOTE_NONNUMERIC)
wr(("a", "", None, 1, 2.5, False), quoting=csv.QUOTE_ALL)
wr(("a", "", None, 1, 2.5, False))
wr(["x", "y z", "'q'"], quoting=csv.QUOTE_ALL, quotechar="'")

print("-- writing: escapechar")
wr(("a", 1, "p,q"), escapechar="\\")
wr(("a", 1, 'p,"q"'), escapechar=None, doublequote=False)
wr(("a", 1, 'p,"q"'), escapechar="\\", doublequote=False)
wr(['"'], escapechar="\\", quoting=csv.QUOTE_MINIMAL)
wr(['"'], escapechar="\\", quoting=csv.QUOTE_MINIMAL, doublequote=False)
wr(['"'], escapechar="\\", quoting=csv.QUOTE_NONE)
wr(("a", 1, "p,q"), escapechar="\\", quoting=csv.QUOTE_NONE)
wr(["\\", "a"], escapechar="\\", quoting=csv.QUOTE_NONE)
wr(["\\", "a"], escapechar="\\", quoting=csv.QUOTE_MINIMAL)
wr(["\\", "a"], escapechar="\\", quoting=csv.QUOTE_ALL)
wr(["\\ ", "a"], escapechar="\\", quoting=csv.QUOTE_MINIMAL)
wr(["\\,", "a"], escapechar="\\", quoting=csv.QUOTE_NONE)
wr([",\\", "a"], escapechar="\\", quoting=csv.QUOTE_MINIMAL)
wr(["C\\", "6", "7", 'X"'], escapechar="\\", quoting=csv.QUOTE_MINIMAL)
wr(["a\nb", "c\rd", '"e"'], escapechar="\\", quoting=csv.QUOTE_NONE)
wr(["a\nb"], quoting=csv.QUOTE_NONE)
wr(['a"b'], quoting=csv.QUOTE_NONE)
wr(['a"b'], quoting=csv.QUOTE_NONE, quotechar=None)
wr(["abc,def"], quoting=csv.QUOTE_NONNUMERIC, escapechar="\\")
wr(['a"b', "c\\d", "e,f"], escapechar="\\", doublequote=False, quoting=csv.QUOTE_ALL)

print("-- writing: lineterminator, empty fields")
for term in ["\r\n", "\n", "\r", "!@#", "\0"]:
    out = Sink()
    w = csv.writer(out, lineterminator=term)
    w.writerow(["a", "b"])
    w.writerow([1, 2])
    w.writerow(["\r", "\n"])
    w.writerow(["x!y", "@", "#z"])
    print(repr("".join(out.parts)))
wr(["a", "b|c", "d"], lineterminator="|")
wr(["xy", "y", "zx"], lineterminator="xy")
nofield: list[str] = []
wr(nofield)
wr([""])
wr([""], quoting=csv.QUOTE_NONE)
wr([""], quoting=csv.QUOTE_STRINGS)
wr([""], quoting=csv.QUOTE_NOTNULL)
nothing: list[str | None] = [None]
nones: list[str | None] = [None, None]
wr(nothing)
wr(nothing, quoting=csv.QUOTE_NONE)
wr(nothing, quoting=csv.QUOTE_STRINGS)
wr(nothing, quoting=csv.QUOTE_NOTNULL)
wr(nothing, quoting=csv.QUOTE_ALL)
wr(["", ""])
wr(nones)
wr([""], delimiter=" ", skipinitialspace=False)
wr([""], delimiter=" ", skipinitialspace=True)
wr(nothing, delimiter=" ", skipinitialspace=True)
wr(["", ""], delimiter=" ")
wr(["", ""], delimiter=" ", skipinitialspace=True)
wr(nones, delimiter=" ", skipinitialspace=True)
wr(["", ""], delimiter=" ", quoting=csv.QUOTE_NONE)
wr(["", ""], delimiter=" ", skipinitialspace=True, quoting=csv.QUOTE_NONE)
for q in [csv.QUOTE_STRINGS, csv.QUOTE_NOTNULL]:
    wr(["", ""], delimiter=" ", quoting=q)
    wr(["", ""], delimiter=" ", skipinitialspace=True, quoting=q)
for q in [csv.QUOTE_NONE, csv.QUOTE_STRINGS, csv.QUOTE_NOTNULL]:
    wr(nones, delimiter=" ", quoting=q)
    wr(nones, delimiter=" ", skipinitialspace=True, quoting=q)
out = Sink()
csv.writer(out).writerow(["X" * 50000, "Y" * 50000])
print(len(out.parts[0]), out.parts[0] == "X" * 50000 + "," + "Y" * 50000 + "\r\n")

print("-- writing: rows of other types")


class Money:
    # a field of the program's class: the writer writes its str()
    def __init__(self, cents: int) -> None:
        self.cents = cents

    def __str__(self) -> str:
        return "%d.%02d" % (self.cents // 100, self.cents % 100)


wr([1, 2, 3])
wr([0.1 * 3, 1e22, -0.0, 1.5])
wr([True, False])
wr(("p, q", 3, 0.5))
wr([Money(1999), Money(5)])
wr([Money(1999)], quoting=csv.QUOTE_NONNUMERIC)
wr([Money(1999)], quoting=csv.QUOTE_STRINGS)
wr(("only",))
wr(("a", "b", "c", "d", "e", "f", "g", "h", "i"))
wr("abc")
wr({"k1": 1, "k2": 2})
wr((1, None, "z"), quoting=csv.QUOTE_NOTNULL)
try:
    csv.writer(Sink()).writerow(5)
except csv.Error as e:
    print("Error:", e)
try:
    csv.writer(Sink()).writerow(None)
except csv.Error as e:
    print("Error:", e)
out = Sink()
w = csv.writer(out)
print(w.writerow(["a"]), w.writerow(["b", "c"]), w.writerows([["d"], ["e", "f"]]), out.parts)
w.writerows([("x", 1), ("y", 2)])
w.writerows(csv.reader(["g,h", "i"]))
print(out.parts)
csv.writer(sys.stdout).writerow(["to", "stdout, a file", 'with "quotes"'])
n = csv.writer(sys.stdout, lineterminator="\n").writerow(["n"])
# a tuple's items, of any types and however many, are each a field
wide = csv.writer(sys.stdout, lineterminator="\n")
wide.writerow(("a", 2, 3.5, None, True, 6, 7, 8, 9, "ten", "e,leven", 12))
wide.writerow((1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30))
wide.writerow(("one",))
wide.writerow((None,))
print(n)

print("-- dialects: checks of the settings")


def bad(kind: str) -> None:
    # make a reader or writer with a bad setting, given by kind
    try:
        if kind == "delimiter=1":
            csv.reader(["a"], delimiter=1)
        elif kind == "delimiter=''":
            csv.reader(["a"], delimiter="")
        elif kind == "delimiter=None":
            csv.reader(["a"], delimiter=None)
        elif kind == "delimiter=':::'":
            csv.writer(Sink(), delimiter=":::")
        elif kind == "quotechar=1":
            csv.reader(["a"], quotechar=1)
        elif kind == "quotechar='ab'":
            csv.reader(["a"], quotechar="ab")
        elif kind == "quotechar=''":
            csv.reader(["a"], quotechar="")
        elif kind == "escapechar=1":
            csv.reader(["a"], escapechar=1)
        elif kind == "escapechar='**'":
            csv.writer(Sink(), escapechar="**")
        elif kind == "lineterminator=None":
            csv.reader(["a"], lineterminator=None)
        elif kind == "lineterminator=1":
            csv.reader(["a"], lineterminator=1)
        elif kind == "quoting=1.0":
            csv.reader(["a"], quoting=1.0)
        elif kind == "quoting=True":
            csv.reader(["a"], quoting=True)
        elif kind == "quoting=99":
            csv.reader(["a"], quoting=99)
        elif kind == "quoting=-1":
            csv.reader(["a"], quoting=-1)
        elif kind == "quoting=2**40":
            csv.reader(["a"], quoting=2**40)
        elif kind == "quoting=None":
            csv.reader(["a"], quoting=None)
        elif kind == "quotechar=None, quoting=MINIMAL":
            csv.reader(["a"], quotechar=None, quoting=csv.QUOTE_MINIMAL)
        elif kind == "excel, quotechar=None":
            csv.reader(["a"], "excel", quotechar=None)
        elif kind == "excel object, quotechar=None":
            csv.reader(["a"], csv.excel, quotechar=None)
        elif kind == "delimiter=newline":
            csv.reader(["a"], delimiter="\n")
        elif kind == "delimiter=CR":
            csv.reader(["a"], delimiter="\r")
        elif kind == "quotechar=space, skipinitialspace":
            csv.reader(["a"], quotechar=" ", skipinitialspace=True)
        elif kind == "escapechar=space, skipinitialspace":
            csv.reader(["a"], escapechar=" ", skipinitialspace=True)
        elif kind == "escapechar=newline":
            csv.reader(["a"], escapechar="\n")
        elif kind == "quotechar=CR":
            csv.reader(["a"], quotechar="\r")
        elif kind == "delimiter in lineterminator":
            csv.reader(["a"], delimiter="x", lineterminator="xy")
        elif kind == "quotechar in lineterminator":
            csv.writer(Sink(), quotechar="!", lineterminator="!\n")
        elif kind == "escapechar in lineterminator":
            csv.writer(Sink(), escapechar="\\", lineterminator="\\\n")
        elif kind == "delimiter=quotechar":
            csv.reader(["a"], delimiter='"')
        elif kind == "delimiter=escapechar":
            csv.reader(["a"], escapechar=",")
        elif kind == "escapechar=quotechar":
            csv.reader(["a"], escapechar='"')
        elif kind == "register 5":
            csv.register_dialect(5)
        elif kind == "register quoting=None":
            csv.register_dialect("nonesuch", quoting=None)
        elif kind == "register badargument":
            csv.register_dialect("nonesuch", badargument=None)
        elif kind == "unregister nonesuch":
            csv.unregister_dialect("nonesuch")
        elif kind == "get nonesuch":
            csv.get_dialect("nonesuch")
        elif kind == "unknown before keywords":
            csv.reader(["a"], "nonesuch", foo=1)
        elif kind == "limit None":
            csv.field_size_limit(None)
        elif kind == "limit str":
            csv.field_size_limit("10")
        elif kind == "limit bool":
            csv.field_size_limit(True)
        print("ok", kind)
    except csv.Error as e:
        print(kind, "| Error:", e)
    except (TypeError, ValueError, OverflowError) as e:
        print(kind, "|", type(e).__name__ + ":", e)


for kind in ["delimiter=1", "delimiter=''", "delimiter=None", "delimiter=':::'", "quotechar=1",
             "quotechar='ab'", "quotechar=''", "escapechar=1", "escapechar='**'",
             "lineterminator=None", "lineterminator=1", "quoting=1.0", "quoting=True", "quoting=99",
             "quoting=-1", "quoting=2**40", "quoting=None", "quotechar=None, quoting=MINIMAL",
             "excel, quotechar=None", "excel object, quotechar=None", "delimiter=newline",
             "delimiter=CR", "quotechar=space, skipinitialspace", "escapechar=space, skipinitialspace",
             "escapechar=newline", "quotechar=CR", "delimiter in lineterminator",
             "quotechar in lineterminator", "escapechar in lineterminator", "delimiter=quotechar",
             "delimiter=escapechar", "escapechar=quotechar", "register 5", "register quoting=None",
             "register badargument", "unregister nonesuch", "get nonesuch", "unknown before keywords",
             "limit None", "limit str", "limit bool"]:
    bad(kind)
print(csv.reader(["a"], quotechar=None).dialect.quoting, csv.reader(["a"], quotechar=None).dialect.quotechar)
print(csv.reader(["a"], escapechar=" ").dialect.escapechar == " ", csv.reader(["a"], delimiter=" ", skipinitialspace=True).dialect.delimiter == " ")
d = csv.reader(["a"], doublequote=None, skipinitialspace="yes", strict=1).dialect
print(d.doublequote, d.skipinitialspace, d.strict)
print(csv.writer(Sink(), lineterminator=":::").dialect.lineterminator)

print("-- dialects: the registry")
print(csv.list_dialects())
for name in csv.list_dialects():
    d = csv.get_dialect(name)
    print(name, repr(d.delimiter), repr(d.quotechar), d.escapechar, d.doublequote, d.skipinitialspace, repr(d.lineterminator), d.quoting, d.strict)
csv.register_dialect("fedcba", delimiter=";")
print(csv.get_dialect("fedcba").delimiter, list(csv.reader(["X;Y;Z"], "fedcba")))
csv.register_dialect("test_dialect", "excel-tab", delimiter=";", quotechar="'", doublequote=False,
                     skipinitialspace=True, lineterminator="\n", quoting=csv.QUOTE_ALL)
d = csv.get_dialect("test_dialect")
print(repr(d.delimiter), repr(d.quotechar), d.doublequote, d.skipinitialspace, repr(d.lineterminator), d.quoting)
csv.register_dialect("tabbed", csv.excel_tab)
csv.register_dialect("piped", dialect="unix", delimiter="|")
print(sorted(csv.list_dialects()))
print(csv.get_dialect("tabbed") is csv.get_dialect("excel-tab"), csv.reader(["a"], "piped").dialect is csv.get_dialect("piped"))
out = Sink()
csv.writer(out, "piped").writerow([1, 2, 3])
csv.writer(out, dialect=csv.get_dialect("test_dialect")).writerow(["a b", "c,d"])
try:
    csv.writer(out, dialect=csv.get_dialect("test_dialect")).writerow(["c'd"])
except csv.Error as e:
    print("Error:", e)
csv.writer(out, csv.excel_tab, delimiter=";").writerow([1, 2, 3])
csv.writer(out, dialect=None).writerow([1, 2, 3])
print(out.parts)
csv.unregister_dialect("fedcba")
csv.unregister_dialect("test_dialect")
csv.unregister_dialect("tabbed")
csv.unregister_dialect("piped")
print(csv.list_dialects())
print(csv.excel.delimiter, csv.excel_tab.delimiter == "\t", csv.unix_dialect.quoting == csv.QUOTE_ALL)
print(csv.QUOTE_MINIMAL, csv.QUOTE_ALL, csv.QUOTE_NONNUMERIC, csv.QUOTE_NONE, csv.QUOTE_STRINGS, csv.QUOTE_NOTNULL, csv.__version__)

print("-- field_size_limit")
old = csv.field_size_limit()
print(old)
big = "X" * 50000
line = big + "," + big
rows = list(csv.reader([line]))
print(len(rows), len(rows[0]), rows[0][0] == big)
print(csv.field_size_limit(50000), csv.field_size_limit())
print(len(list(csv.reader([line]))[0]))
csv.field_size_limit(49999)
rd([line])
rd(['"' + "X" * 49999 + '"'])
rd(['"' + "X" * 49999 + '""'])
rd(['"' + "X" * 49999 + '"', "x"])
rd(['"' + "X" * 49990 + "\n", "Y" * 10 + '"'])
rd(["X" * 49999 + "\\"], escapechar="\\")
csv.field_size_limit(3)
rd(["abc,de"])
rd(["abcd"])
rd(['"ab""c"'])
rd(['"ab""cd"'])
rd(["éé,€€€"])
rd(["éééé"])
csv.field_size_limit(0)
rd(["", ",", '""'])
rd(["a"])
print(csv.field_size_limit(old))

print("-- DictReader")
for drow in csv.DictReader(["name,age\n", "bob,3\n", "\n", "amy,5\n"]):
    print(drow)
dr = csv.DictReader(["f1,f2,f3\r\n", "1,2,abc\r\n"])
print(dr.fieldnames)
print(list(dr), dr.line_num, list(dr))
print(list(csv.DictReader(["1,2,abc\r\n"], fieldnames=["f1", "f2", "f3"])))
print(list(csv.DictReader(["1,2,abc,4,5,6\r\n"], "1 2 3 4 5 6".split())))
print(list(csv.DictReader(["1,2,abc\r\n", "1,2,abc,4,5,6\r\n"], fieldnames="1 2 3 4 5 6".split(), restval="DEFAULT")))
print(list(csv.DictReader(["2147483648,43.0e12,17,abc,def\r\n", "147483648,43.0e2,17,abc,def\r\n"], fieldnames="i1 float i2 s1 s2".split())))
print(list(csv.DictReader(["1,2,abc,4,5,6\r\n", "\r\n", "1,2,abc,4,5,6\r\n"], fieldnames="1 2 3 4 5 6".split())))
print(list(csv.DictReader(["1;2;abc;4;5;6\r\n"], fieldnames="1 2 3 4 5 6".split(), delimiter=";")))
print(list(csv.DictReader(["a\tb", "1\t2"], dialect="excel-tab")), list(csv.DictReader(["a|b", "1|2"], dialect=csv.excel, delimiter="|")))
dr = csv.DictReader(["a,a,b", "1,2,3"])
print(dr.fieldnames, list(dr))
dr = csv.DictReader(["x,y", "1,2", "", "", "3,4", "", ""])
print(list(dr), dr.line_num, dr.reader.line_num)
dr = csv.DictReader(["x,y", "1,2", "", "3,4"])
print(list(dr), dr.line_num)
dr = csv.DictReader(["x,y"])
print(dr.fieldnames, list(dr), dr.line_num)
dr = csv.DictReader(noline)
print(dr.fieldnames, list(dr), dr.line_num)
dr = csv.DictReader(["", "a,b", "1,2"])
print(dr.fieldnames)
dr = csv.DictReader(["h1,h2", '"multi\nline",2', "3,4"])
print(list(dr), dr.line_num)
dr = csv.DictReader(["1,2", "3,4"], ["a", "b"])
dr.fieldnames = ["A", "B"]
print(list(dr), dr.fieldnames)
try:
    print(list(csv.DictReader(["a,b", '"c'], strict=True)))
except csv.Error as e:
    print("Error:", e)

print("-- DictWriter")
out = Sink()
dw = csv.DictWriter(out, fieldnames=["f1", "f2", "f3"])
print(dw.writeheader())
print(dw.writerow({"f1": "10", "f3": "abc"}))
dw.writerows([{"f1": "1", "f2": "abc", "f3": "f"}, {"f1": "2", "f2": "5", "f3": "xyz"}])
print(out.parts)
out = Sink()
dwi = csv.DictWriter(out, ["f1", "f2", "f3"], lineterminator="\n")
dwi.writerow({"f1": 1, "f3": 3})
dwi.writerow({"f2": 2})
print(out.parts)
out = Sink()
try:
    csv.DictWriter(out, ["f1", "f2", "f3"]).writerow({"f4": "10", "f2": "spam"})
except ValueError as e:
    print("ValueError:", e)
try:
    csv.DictWriter(out, ["f1", "f2"], extrasaction="raised")
except ValueError as e:
    print("ValueError:", e)
for action in ["raise", "RAISE", "ignore", "IGNORE"]:
    out = Sink()
    try:
        csv.DictWriter(out, ["f1", "f2"], extrasaction=action).writerow({"f1": 1, "f2": 2, "f3": 3})
        print(action, out.parts)
    except ValueError as e:
        print(action, "ValueError:", e)
out = Sink()
dwt = csv.DictWriter(out, ("a", "b"), restval="-", dialect="unix", quoting=csv.QUOTE_MINIMAL)
dwt.writeheader()
dwt.writerow({"a": "x,y"})
optional: dict[str, str | None] = {"a": None, "b": "z"}
dwt.writerow(optional)
print(out.parts)
out = Sink()
dwn = csv.DictWriter(out, ["a"], restval=None, quoting=csv.QUOTE_NOTNULL)
try:
    dwn.writerow({"b": "x"})
except ValueError as e:
    print("ValueError:", e)
dwn.extrasaction = "ignore"
try:
    dwn.writerow({"b": "x"})
except csv.Error as e:
    print("Error:", e)

print("-- round trips through files")
tmp = tempfile.mkdtemp()
path = os.path.join(tmp, "data.csv")
rows = [["\na", "b\nc", "d\n"], ["\re", "f\rg", "h\r"], ["\r\ni", "j\r\nk", "l\r\n"],
        ["\n\rm", "n\n\ro", "p\n\r"], ["\r\rq", "r\r\rs", "t\r\r"], ["\n\nu", "v\n\nw", "x\n\n"],
        ['"quoted"', "a,b", "", " lead", "trail ", "é€"]]
for term in ["\r\n", "\n", "\r"]:
    with open(path, "w", newline="") as f:
        csv.writer(f, lineterminator=term).writerows(rows)
    with open(path, newline="") as f:
        back = list(csv.reader(f))
    print(repr(term), back == rows)
    with open(path, "w", newline="") as f:
        csv.writer(f, lineterminator=term, quoting=csv.QUOTE_NONE, escapechar="\\").writerows(rows)
    with open(path, newline="") as f:
        back = list(csv.reader(f, quoting=csv.QUOTE_NONE, escapechar="\\"))
    print(repr(term), back == rows)
with open(path, "w", newline="") as f:
    fw = csv.writer(f)
    fw.writerow(["id", "text"])
    fw.writerow((1, "line one\nline two"))
    fw.writerow((2, 'say "hi", then go'))
with open(path, newline="") as f:
    print(repr(f.read()))
with open(path, newline="") as f:
    print(list(csv.reader(f)))
with open(path) as f:
    print(list(csv.reader(f)))
with open(path, newline="") as f:
    for drow in csv.DictReader(f):
        print(drow["id"], repr(drow["text"]))
os.remove(path)
os.rmdir(tmp)

print("-- characters past ASCII")
rd(["é,€,ü\n", '"日本,語","a""é"\n'])
rd(["a§b§c", "§§"], delimiter="§")
rd(["€a€,€b€€c€"], quotechar="€")
rd(["a¤,b,¤¤,c¤"], escapechar="¤")
rd(["x¦y"], delimiter="¦", quotechar="¤", escapechar="€")
rd(["€", "é"], delimiter="€")
rd(["a€b"], delimiter="€", strict=True)
rd(['"a"€b'], delimiter="€", strict=True)
rd(['"a"b'], delimiter="€", strict=True)
wr(["é", "a€b", "c§d"], delimiter="§")
wr(['"€"', "x"], quotechar="€")
wr(["a€b", "c"], quotechar="€", doublequote=False, escapechar="\\")
wr(["a¤b", "c§d"], delimiter="§", quoting=csv.QUOTE_NONE, escapechar="¤")
wr(["é\u2028", "x"], lineterminator="\u2028")
for c in ["é", "€", "§", "𝄞"]:
    print(repr(csv.reader(["a"], delimiter=c).dialect.delimiter))
bad_chars = ["éé", "€x"]
for c in bad_chars:
    try:
        csv.reader(["a"], delimiter=c)
    except TypeError as e:
        print("TypeError:", e)

print("-- random rows, written and read back")
seed = 20261013


def rand(n: int) -> int:
    # an int in [0, n): a 31-bit linear congruential generator (glibc's constants)
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return (seed >> 8) % n


# (the delimiters, quotechars and escapechars are three sets apart, and the fields hold them all)
ALPHABET = ["a", "b", " ", ",", ";", "\t", "§", '"', "'", "|", "\\", "~", "€", "\n", "\r", "é", "x y", ""]
DELIMITERS = [",", ";", "\t", " ", "§"]
QUOTECHARS = ['"', "'", "|"]
ESCAPECHARS: list[str | None] = [None, "\\", "~", "€"]
TERMINATORS = ["\r\n", "\n", "\r", "\r\n", "\n"]
QUOTINGS = [csv.QUOTE_MINIMAL, csv.QUOTE_ALL, csv.QUOTE_NONE, csv.QUOTE_NOTNULL, csv.QUOTE_STRINGS]
same = 0
for case in range(300):
    fields: list[list[str]] = []
    for _ in range(1 + rand(3)):
        fs: list[str] = []
        for _ in range(1 + rand(4)):
            text = ""
            for _ in range(rand(5)):
                text += ALPHABET[rand(len(ALPHABET))]
            fs.append(text)
        fields.append(fs)
    delimiter = DELIMITERS[rand(len(DELIMITERS))]
    quotechar = QUOTECHARS[rand(len(QUOTECHARS))]
    escapechar = ESCAPECHARS[rand(len(ESCAPECHARS))]
    doublequote = rand(3) != 0
    skip = rand(3) == 0
    term = TERMINATORS[rand(len(TERMINATORS))]
    quoting = QUOTINGS[rand(len(QUOTINGS))]
    out = Sink()
    try:
        w = csv.writer(out, delimiter=delimiter, quotechar=quotechar, escapechar=escapechar,
                       doublequote=doublequote, skipinitialspace=skip, lineterminator=term,
                       quoting=quoting)
        w.writerows(fields)
        text = "".join(out.parts)
        r = csv.reader(text.splitlines(True), delimiter=delimiter, quotechar=quotechar,
                       escapechar=escapechar, doublequote=doublequote, skipinitialspace=skip,
                       quoting=csv.QUOTE_NONE if quoting == csv.QUOTE_NONE else csv.QUOTE_MINIMAL)
        back = list(r)
        if back == fields:
            same += 1
            print(case, repr(text), r.line_num)
        else:
            print(case, repr(text), "->", back)
    except csv.Error as e:
        print(case, fields, "Error:", e)
print(same, "read back as written")

print("-- random lines, read")
CHUNKS = ["a", "bc", ",", ";", '"', "'", "\\", " ", "é", "€", "|", '""', "x", "\t", "~"]
ENDS = ["", "\n", "\r\n", "\r", "\n"]
for case in range(300):
    lines = []
    for _ in range(rand(4)):
        text = ""
        for _ in range(rand(8)):
            text += CHUNKS[rand(len(CHUNKS))] if rand(12) != 0 else ["\n", "\r"][rand(2)]
        lines.append(text + ENDS[rand(len(ENDS))])
    delimiter = DELIMITERS[rand(len(DELIMITERS))]
    quotechar = QUOTECHARS[rand(len(QUOTECHARS))]
    escapechar = ESCAPECHARS[rand(len(ESCAPECHARS))]
    print(case, repr(lines), end=" ")
    rd(lines, delimiter=delimiter, quotechar=quotechar, escapechar=escapechar,
       doublequote=rand(3) != 0, skipinitialspace=rand(2) == 0, strict=rand(3) == 0,
       quoting=[csv.QUOTE_MINIMAL, csv.QUOTE_ALL, csv.QUOTE_NONE][rand(3)])
