# lib/re: CPython 3.13's re (its parser and compiler, and _sre's engine) ported to the subset;
# each result is compared with CPython's own re
import re


def show(m) -> str:
    if m is None:
        return "None"
    return "%s %r last=%s/%s" % (m.span(), m.group(0), m.lastindex, m.lastgroup)


def err(p: str, flags: int = 0) -> None:
    try:
        re.compile(p, flags)
        print("ok", repr(p))
    except re.error as e:
        print("error", repr(p), "|", e.msg, e.pos, e.lineno, e.colno, "|", e)
    except OverflowError as e:
        print("OverflowError", repr(p), e)
    except ValueError as e:
        print("ValueError", repr(p), e)


print("-- compile, Pattern")
p = re.compile(r"(?P<year>\d{4})-(?P<month>\d\d)(?:-(?P<day>\d\d))?")
print(p)
print(p.pattern, p.flags, p.groups, dict(p.groupindex))
print(re.compile("a", re.I | re.M), re.compile("(?s)x"), re.compile("b", re.A), re.compile("c", re.X | re.S))
print(re.compile("x" * 300) == re.compile("x" * 300), re.compile("a") == re.compile("a", re.I))
print(re.compile("q") is re.compile("q"))
print(re.compile(p) is p, re.compile("y" * 250))

print("-- Match")
m = p.search("on 2024-05-17 and 1999-12")
print(m)
if m is not None:
    print(m.group(), m.group(0), m.group(1), m.group("month"), m.group(1, "day", 2))
    print(m[0], m["year"], m[3], m.groupdict(), m.groupdict("--"))
    print(m.start(), m.end(), m.span(), m.start(2), m.end("day"), m.span("year"))
    print(m.pos, m.endpos, m.lastindex, m.lastgroup, m.string, m.re is p)
    print(m.expand(r"\g<day>.\g<2>.\1 (\g<0>)"))
m2 = p.search("1999-12 only")
print(m2)
if m2 is not None:
    print(m2.group("day"), m2.span(3), m2.start("day"), m2.groupdict(), m2.lastgroup)
    print(repr(m2.expand(r"[\3]")))

print("-- match, fullmatch, search, pos and endpos")
q = re.compile(r"\w+")
for s in ["hello world", "  x", ""]:
    print(repr(s), show(q.match(s)), show(q.fullmatch(s)), show(q.search(s)))
print(show(q.match("hello world", 6)), show(q.match("hello world", 3, 5)), show(q.search("hello world", 5)))
print(show(q.fullmatch("hello world", 6, 11)), show(q.fullmatch("hello world", 6, 10)), show(q.search("ab", 5)))
print(show(q.search("hello", -3, 99)), show(q.match("hello", 4, 2)), show(re.compile("$", re.M).match("a\nb", 1, 0)))
print(show(re.match("a+", "aaab")), show(re.fullmatch("a+b", "aaab")), show(re.search("b+", "aaabbbc")))

print("-- findall, finditer")
print(re.findall(r"\d+", "a1b22c333"), re.findall(r"(\d)\d*", "a1b22c333"), re.findall("x*", "axxb"))
print(re.findall(r"\b\w", "the quick brown"), re.findall("", "abc"), re.findall("(a)|b", "ab"))
print([mm.span() for mm in re.finditer(r"\w+", "one two  three")], [mm.group() for mm in re.finditer("a*", "baac")])
print(q.findall("a bc def", 2), [mm.start() for mm in q.finditer("a bc def", 0, 5)])

print("-- split")
print(re.split(r"\W+", "Words, words, words."), re.split(r"(\W+)", "Words, words, words."))
print(re.split(r"\W+", "Words, words, words.", maxsplit=1), re.split("x*", "axbc"), re.split(r"\b", "a b"))
print(re.split("[a-f]+", "0a3B9", flags=re.I), re.split(",", ""), re.split("^$", "a\n\nb", flags=re.M))

print("-- sub, subn")
print(re.sub(r"(\w+)@(\w+)", r"\g<2> at \g<1>", "me@host you@there"), re.sub("x*", "-", "abxd"))
print(re.subn("a", "b", "banana"), re.sub("a", "b", "banana", count=2), re.subn("(?i)A", r"[\g<0>]", "aAb"))
print(re.sub(r"(?P<n>\d+)", lambda mm: str(int(mm.group("n")) * 2), "a1 b22 c333"))
print(repr(re.sub(r"\d", r"\n\t\\", "1")), re.sub("", "-", "ab"))
print(re.sub(r"(a)(b)?", r"[\1|\2]", "ab a"), re.sub("b", lambda mm: mm.group().upper() + "!", "abcb"))
print(re.sub(r"\s+", " ", "  many   spaces\there "), re.sub("(?m)^", "> ", "one\ntwo"))
print(q.sub("W", "ab cd", 1), q.subn(lambda mm: "(" + mm.group() + ")", "ab cd"))

print("-- syntax")
for pat, s in [(r"a{2,3}", "aaaa"), (r"a{,2}b", "aaab"), (r"a{2,}?", "aaaa"), (r"(?:ab)+", "ababa"),
               (r"a+?b", "aaab"), (r"a*+a", "aaa"), (r"(?>a+)b", "aab"), (r"a++b", "aaab"), (r"[\b]", "a\bb"),
               (r"(\w)\1", "abccd"), (r"(?P<c>.)(?P=c)", "xyyz"), (r"(?<=\$)\d+", "cost $42"),
               (r"(?<!a)b", "abcb"), (r"\d+(?=px)", "10em 20px"), (r"q(?!u)", "quit qat"), (r"(a)?(?(1)b|c)", "xc"),
               (r"(?P<q>')?\w+(?(q)')", "'hi'"), (r"\Aab|cd\Z", "cd"), (r"\Bb\B", "abc b"), (r"[^a-c]+", "abcdefa"),
               (r"[\w.-]+@[\w.-]+", "mail me@ex.com!"), (r"[\x41-\x43]+", "ABCD"), (r"A\U00000042", "AB"),
               (r"\101\0", "A\0"), (r"[]a]+", "a]]b"), (r"[a-]+", "-a-"), (r"(?x) a  b  # comment", "ab"),
               (r"(?i:A)a", "aa Aa aA"), (r"(?-i:a)b", "Ab"), (r"a|b|c", "xyzc"), (r"ab|ac", "ac"),
               (r"(a|ab)(c|bcd)(d*)", "abcd"), (r"(a*)*b", "aab"), (r"(a*)+", "b"), (r"x{0}y", "y"), (r"\.\*", "a.*b")]:
    print(repr(pat), show(re.search(pat, s)), show(re.search(pat, s, re.I)))

print("-- flags")
print(show(re.search("^b", "a\nb")), show(re.search("^b", "a\nb", re.M)), show(re.search("a$", "a\nb", re.M)))
print(show(re.search("a.b", "a\nb")), show(re.search("a.b", "a\nb", re.S)), show(re.search("a$", "a\n")))
print(show(re.search(r"(?i)hello", "Say HeLLo")), show(re.search(r"[A-Z]+", "abc", re.I)), show(re.search("(?m)b$", "ab\nc")))
print(re.findall(r"(?a)\w+", "abc d_e"), re.findall("(?a:[a-z]+)", "Hi there"), int(re.I), int(re.M | re.S))

print("-- non-ASCII text")
for pat, s in [("é", "café"), (r"\w+", "naïve résumé"), (r"(?i)É+", "éÉé!"), (r"\d+", "a١٢٣b45"), (r"\s", "a\xa0b"),
               (r"\w+", "€uro"), (".", "☃"), (r"[à-ÿ]+", "voilà ça"), ("(?i)straße", "STRASSE"), ("(?i)k", "K"),
               ("(?i)[ſ]", "S"), (r"(?a)\w+", "héllo"), (r"\W", "aé b"), ("𝔄+", "x𝔄𝔄y"), ("[^a]", "aé")]:
    mm = re.search(pat, s)
    if mm is None:
        print(repr(pat), "None")
    else:
        print(repr(pat), repr(mm.group()), s[mm.start():mm.end()] == mm.group(), s.find(mm.group()) == mm.start(),
              s[mm.end():])
print(re.findall(".", "naïve☃𝔄"), re.split("é", "aébéc"), re.sub("(?i)ö", "o", "Köln KÖLN"))
print(re.sub(r"\w", lambda mm: "<" + mm.group() + ">", "aé"), len(re.findall(r"\w", "日本語")))

print("-- escape, purge")
print(re.escape("a,b c.d*e(f)g\n"), re.escape("http://ex.com/?q=1&r=[2]"), re.escape(""))
print(show(re.search(re.escape("1+1=2?"), "is 1+1=2?")))
re.purge()
print(re.compile("x+") == re.compile("x+"))

print("-- errors")
for pat in ["(", ")", "a)", "(?", "(?P<1a>x)", "(?P<a>x)(?P<a>y)", "(?P=b)", "[", "[z-a]", "a**", "*a", "x{2,1}",
            r"\8", r"\777", r"\q", "\\", "(?i", "(?z)", "(?<=a+)", "(?(1)a|b|c)", "(?(2)a)(b)", r"(a)\2", "(?P<a",
            "(?<x>y)", "(?#abc", "a\n(b", "ab\ncd\n(?P", "a(?i)b", "(?-a:x)", r"\x4", r"\u12g", r"\U0011ffff",
            "(?P<é>x)(?P=é)", "(?P<¹>x)", r"\g<1>", "[\\d-z]", "(?<!a|bc)", "(?L)x", "(?au)x"]:
    err(pat)
err("x", re.L)
err("x", re.A | re.U)
err("a{4294967296}")
err("a{0000000000004}")
try:
    re.compile(p, re.I)
except ValueError as e:
    print("ValueError:", e)
try:
    re.sub("(a)", r"\2", "a")
except re.error as e:
    print("error:", e)
try:
    re.sub("(?P<a>x)", r"\g<b>", "x")
except IndexError as e:
    print("IndexError:", e)
mm = re.match("(a)", "a")
if mm is not None:
    try:
        print(mm.group(2))
    except IndexError as e:
        print("IndexError:", e)
    try:
        print(mm.group("z"))
    except IndexError as e:
        print("IndexError:", e)

print("-- a parser's loop: match at each position of one string")
tok = re.compile(r"\s*(?:(\d+)|(\w+)|(.))")
src = "x1 = 42 + foo(7)"
i = 0
out: list[str] = []
while i < len(src):
    t = tok.match(src, i)
    if t is None:
        break
    li = t.lastindex
    out.append("%s:%s" % (li, t.group(li) if li is not None else t.group(0)))
    i = t.end()
print(" ".join(out))
