import re


def show(label: str, f) -> None:
    try:
        print(label, f())
    except Exception as e:
        print(label, type(e).__name__, e)


def m(pat: str, s: str, flags: int = 0) -> str:
    try:
        r = re.search(pat, s, flags)
    except re.error as e:
        return f"error {e}"
    if r is None:
        return "None"
    return f"{r.span()} {r.group()!r} {r.groups()!r}"


CASES: list[tuple[str, str]] = [
    (r"a*", "aaa"), (r"a*?", "aaa"), (r"a+?b", "aaab"), (r"(a|ab)(c|bcd)(d*)", "abcd"), (r"(a+)+b", "aaaaaaaaaaaaaaaaaaaaaaac"),
    (r"^(\d{3})-(\d{2,4})$", "123-4567"), (r"\bfoo\b", "a foo b"), (r"\Bfoo", "afoo"), (r"(?i)straSSe", "STRASSE"), (r"(?i)ß", "SS"),
    (r"(?P<y>\d{4})-(?P<m>\d\d)", "on 2024-05-06"), (r"(a)(?:b)(c)?", "ab"), (r"(a)|(b)", "b"), (r"((a)|(b))+", "ab"), (r"(?:(a)|b)*", "ab"),
    (r"x(?=y)", "xy"), (r"x(?!y)", "xyxz"), (r"(?<=a)b", "ab"), (r"(?<!a)b", "ab cb"), (r"(?<=\d{2})x", "12x"), (r"(a)\1", "aa"), (r"(?P<q>['\"]).*?(?P=q)", "say 'hi' \"yo\""),
    (r"[a-c]+", "xabcx"), (r"[^a-c]+", "abcxyz"), (r"[\d\s]+", "a1 2b"), (r"[]a]+", "]a]"), (r"[a\]]+", "a]"), (r"[\w.-]+@[\w.-]+", "mail bob.x@ex-ample.org now"),
    (r"\d+\.\d*|\.\d+", "x .5 y 3."), (r"a{2}", "aaa"), (r"a{2,}", "aaaa"), (r"a{,2}", "aaa"), (r"a{2,3}?", "aaaa"), (r"a{0}", "a"), (r"(ab){2}", "ababab"),
    (r".", "\n"), (r"(?s).", "\n"), (r"^b", "a\nb"), (r"(?m)^b", "a\nb"), (r"a$", "a\n"), (r"(?m)a$", "a\nb"), (r"a\Z", "a\n"), (r"\Aa", "ba"),
    (r"(?x) a  b # comment\n c", "abc"), (r"é+", "ééé"), (r"\w+", "héllo wörld"), (r"(?a)\w+", "héllo"), (r"\s+", "a\u00a0\u2003b"), (r"[α-ω]+", "xαβγy"),
    (r"(?i)é", "É"), (r"(?i)[a-z]+", "ABCdef"), (r"\u00e9", "é"), (r"\x41\101", "AA"), (r"[\u4e00-\u9fff]+", "漢字kana"),
    (r"(a*)*", "b"), (r"(a*)+", "b"), (r"(a|b)*?c", "abac"), (r"(?:a|b)+?(?=c)", "abc"), (r"a(?#comment)b", "ab"), (r"(?:)", ""), (r"()", ""), (r"a||b", "b"),
    (r"(", "x"), (r")", "x"), (r"[a", "x"), (r"a**", "x"), (r"(?P<n>a)(?P<n>b)", "ab"), (r"\1(a)", "aa"), (r"(?<=a+)b", "ab"), (r"a{3,2}", "aaa"), (r"[z-a]", "x"), (r"\q", "q"), (r"(?z)", "x"), (r"*a", "a"), (r"a\\", "a\\"), ("a\\", "a"),
    (r"(a)(b)?(c)?", "ac"), (r"(?:(?P<x>a)|(?P<y>b))+", "ab"), (r"(a(b(c)))", "abc"), (r"(?=(a+))a*b\1", "baaabac"), (r"^(?:(a)|c)(?(1)b|d)$", "ab"), (r"^(?:(a)|c)(?(1)b|d)$", "cd"), (r"^(?:(a)|c)(?(1)b|d)$", "ad"),
    (r"\d{1,3}(?:,\d{3})*", "x 1,234,567 y"), (r"(\w)(\w)\2\1", "abba"), (r"(?i)(a)\1", "aA"), (r"[\s\S]{3}", "a\nb"), (r"[^\n]*", "ab\ncd"), (r"a.*?b|c", "c a b"), (r"(?:a|ab)c", "abc"), (r"(a?)*?b", "aab"),
    (r"(?>a+)b", "aaab"), (r"a++b", "aaab"), (r"a*+a", "aaa"), (r"(?>a|ab)c", "abc"), (r"a?+a", "a"), (r"x{2}+", "xxxx"),
]


def main() -> None:
    for i, (pat, s) in enumerate(CASES):
        print(i, repr(pat), repr(s), m(pat, s))
    p = re.compile(r"(?P<key>\w+)=(?P<val>[^;]*)")
    show('match', lambda: re.match(r"\d+", "12a").group())
    show('match2', lambda: re.match(r"\d+", "a12"))
    show('match3', lambda: re.fullmatch(r"\d+", "12a"))
    show('match4', lambda: re.fullmatch(r"\d+", "12").group())
    show('findall1', lambda: re.findall(r"\d+", "a1b22c333"))
    show('findall2', lambda: re.findall(r"(\w)=", "a=1,b=2"))
    show('findall3', lambda: re.findall(r"a*", "baac"))
    show('findall4', lambda: re.findall(r"", "ab"))
    show('findall5', lambda: re.findall(r"\b", "ab cd"))
    show('findall6', lambda: re.findall(r"(a)(b)", "abab"))
    show('finditer', lambda: [(x.start(), x.end(), x.group()) for x in re.finditer(r"a|", "bab")])
    show('sub1', lambda: re.sub(r"a", "b", "aaa", 2))
    show('sub2', lambda: re.sub(r"(\w+) (\w+)", r"\2 \1", "hello world"))
    show('sub3', lambda: re.sub(r"x*", "-", "abxd"))
    show('sub4', lambda: re.sub(r"", "-", "abc"))
    show('sub5', lambda: re.sub(r"(?P<n>a)", r"[\g<n>]", "cat"))
    show('sub6', lambda: re.sub(r"a", r"\\", "cat"))
    show('sub7', lambda: re.sub(r"(a)", r"\g<1>0", "cat"))
    show('sub8', lambda: re.sub(r"\s+", " ", " a \n b  "))
    show('sub9', lambda: re.sub(r"a|(b)", r"[\1]", "ab"))
    show('sub10', lambda: re.sub(r"(?i)hello", "X", "Hello HELLO hello"))
    show('sub11', lambda: re.sub(r"a", r"\n\t\x", "a"))
    show('sub12', lambda: re.sub(r"a", "\\n", "a"))
    show('sub fn', lambda: re.sub(r"\d+", lambda x: str(int(x.group()) * 2), "a1b22c333"))
    show('subn1', lambda: re.subn(r"a", "b", "banana"))
    show('subn2', lambda: re.subn(r"z", "b", "banana"))
    show('subn3', lambda: re.subn(r"a", "", "banana", count=2))
    show('sub bad', lambda: re.sub(r"a", r"\9", "a"))
    show('sub bad2', lambda: re.sub(r"a", r"\g<x>", "a"))
    show('split1', lambda: re.split(r",\s*", "a, b,c"))
    show('split2', lambda: re.split(r"(,)", "a,b"))
    show('split3', lambda: re.split(r"x*", "axbc"))
    show('split4', lambda: re.split(r"\b", "a b"))
    show('split5', lambda: re.split(r",", "a,b,c", 1))
    show('split6', lambda: re.split(r"", "abc"))
    show('split7', lambda: re.split(r"(?<=,)", "a,b,c"))
    show('split8', lambda: re.split(r"(a)|(b)", "xaybz"))
    show('escape', lambda: re.escape("a.b*c[d]{e}|f g\n-é#&~"))
    show('flags1', lambda: m(r"abc", "ABC", re.I))
    show('flags2', lambda: m(r"^b$", "a\nb\nc", re.M))
    show('flags3', lambda: m(r"a.b", "a\nb", re.S))
    show('flags4', lambda: m(r"a b", "ab", re.X))
    show('flags5', lambda: m(r"\w+", "é", re.A))
    show('flags6', lambda: m(r"a.b", "A\nB", re.I | re.S))
    show('compiled1', lambda: (p.pattern, p.groups, p.groupindex["val"], p.flags & re.I))
    show('compiled2', lambda: p.search("x; a=1; b=two").groupdict())
    show('compiled3', lambda: [mm.group("key", "val") for mm in p.finditer("a=1;b=;c=3")])
    show('match bool', lambda: (bool(re.search("a", "a")), re.search("a", "b") is None))
    show('pos1', lambda: p.match("a=1", 1))
    show('pos2', lambda: re.compile("^a").search("ba", 1))
    show('pos3', lambda: re.compile("a$").search("ab", 0, 1).span())
    show('pos4', lambda: re.compile(r"\b").search("ab", 1).span())
    show('lastindex', lambda: (re.match(r"(a)(b)?", "a").lastindex, re.match(r"(a)|(b)", "b").lastindex, re.match(r"((a)(b))", "ab").lastindex, re.match(r"a", "a").lastindex))
    show('groups1', lambda: re.match(r"(a)(b)?", "a").groups())
    show('groups2', lambda: re.match(r"(a)(b)?", "a").groups("x"))
    show('groups3', lambda: re.match(r"(a)(b)?", "a").group(2))
    show('groups4', lambda: re.match(r"(a)(b)?", "a").span(2))
    show('groups5', lambda: re.match(r"(a)(b)?", "a").start(2))
    show('no group', lambda: re.match(r"(a)", "a").group(2))
    show('no name', lambda: re.match(r"(a)", "a").group("x"))
    show('ucls1', lambda: re.findall(r"\d", "1२٣"))
    show('ucls2', lambda: re.findall(r"(?a)\d", "1२٣"))
    show('ucls3', lambda: re.findall(r"\W", "a-é b"))
    show('ucls4', lambda: re.findall(r"\S+", "a\u3000b"))
    show('ucls5', lambda: re.findall(r"[^\W\d_]+", "abc123_dé"))
    show('icase1', lambda: re.findall(r"(?i)σ", "Σσς"))
    show('icase2', lambda: re.findall(r"(?i)k", "K\u212a"))
    show('icase3', lambda: re.findall(r"(?i)[a-z]", "\u017f\u212a"))
    show('icase4', lambda: re.findall(r"(?i)i", "İIıi"))
    show('icase5', lambda: re.findall(r"(?i)ǆ", "ǅǄ"))
    show('icase6', lambda: re.findall(r"(?i)[à-þ]+", "ÀÉÎ×õ"))
    show('long1', lambda: len(re.findall(r"a", "a" * 20000)))
    show('long2', lambda: re.search(r"(a|b)*c", "ab" * 5000 + "c").end())
    show('long3', lambda: re.search(r"(?:a|b)*c", "ab" * 50000 + "c").end())
    show('long4', lambda: len(re.sub(r"a+", "b", "a" * 100000)))
    show('long5', lambda: re.search(r"(?:\w+\s?)*$", "word " * 3000).end())
    show('backtrack', lambda: m(r"(x+x+)+y", "x" * 22))
    show('purge', lambda: re.purge())
    mm = p.search("zz a=1; b=two", 5)
    if mm is not None:
        show("mo1", lambda: (mm.start(), mm.end(), mm.span(1), mm.span("val")))
        show("mo2", lambda: mm.group(0, 1, 2))
        show("mo3", lambda: (mm["key"], mm[2], mm.lastindex, mm.lastgroup, mm.pos, mm.endpos, mm.string, mm.re.pattern))
        show("mo4", lambda: mm.expand(r"\1->\g<val>"))
        show("mo5", lambda: repr(mm))


main()
