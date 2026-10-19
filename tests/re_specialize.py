# lib/re with matchers generated for this program's patterns: tests/re_specialize.path puts
# tests/re_specialize_matchers/ first on the import path, where tools/re_specialize.py wrote them from
# a profile of this program under CPython (tools/test_re_specialize.py checks that they are as it
# writes them). They must give CPython's results: spans, groups, lastindex and lastgroup, findall,
# finditer, split and sub, on ASCII subjects, which the matchers read in place, and on others, which
# they decline (lib/re's interpreter runs), as they decline group repeats nested deeper than they go.
import fnmatch
import re
from html.parser import HTMLParser


def show(m: re.Match | None) -> None:
    if m is None:
        print(None)
        return
    print(m.span(), [m.span(i) for i in range(1, m.re.groups + 1)], m.lastindex, m.lastgroup)


CASES: list[tuple[str, int, list[str]]] = [
    (r"(\d{4})-(\d{2})-(\d{2})", 0, ["on 2026-10-19 and 1999-01-02.", "2026-1-19", ""]),
    (r"[&<]", 0, ["<p>Tom &amp; Jerry</p>", "plain"]),
    (r"[A-Za-z_][A-Za-z0-9_]*", 0, ["def f_1(a, b2): return a", "123"]),
    (r"\s*(\w+)\s*=\s*(\d+)\s*$", 0, ["  key_1 = 42  ", "# comment", "k=7\n"]),
    (r"(a)x|.(c)", 0, ["ac", "axc"]),
    (r"(?:(a)|b)*", 0, ["ab", "ba", ""]),
    (r"((a)|b)+", 0, ["ab", "bab"]),
    (r"(a*)*", 0, ["aa", "ab"]),
    (r"(a|b)*?c", 0, ["abc", "abab"]),
    (r"(?P<x>a)(?P=x)", 0, ["aa", "xaab"]),
    (r"(?i)(a)\1", 0, ["aA", "ab"]),
    (r"(?:ab)++c", 0, ["ababc", "abab"]),
    (r"(?>a|ab)c", 0, ["abc", "ac"]),
    (r"(?<=a)b|(?<!a)c", 0, ["abc", "cb"]),
    (r"(?=(\w+))\w", 0, ["ab cd"]),
    (r"\bfoo\b", 0, ["foo bar foo.", "foobar"]),
    (r"^line$", re.M, ["line\nline\n", "xline"]),
    (r"a.c", re.S, ["a\nc", "abc"]),
    (r"(?i)hello", 0, ["Hello HELLO", "help"]),
    (r"x{2,3}?y", 0, ["xxxy xxy xy"]),
    (r"x*", 0, ["axxb", ""]),
    (r"(?:ab)*c", 0, ["ab" * 3 + "c", "ab" * 1100 + "c"]),
    (r"(a)?(?(1)b|c)", 0, ["ab", "c"]),
]

for pattern, flags, subjects in CASES:
    r = re.compile(pattern, flags)
    print(repr(r))
    for s in subjects + ["é" + subjects[0]]:
        show(r.search(s))
        show(r.match(s))
        show(r.fullmatch(s))
        show(r.search(s, 1, len(s) - 1))
        print([m.span() for m in r.finditer(s)])
        if r.groups <= 1:
            print(r.findall(s))
        if r.groups == 0:
            print(r.split(s))
        print(r.subn("<\\g<0>>", s))
        print(r.sub(lambda m: str(m.span()), s, 2))


# HTMLParser's patterns, on a document of each kind of tag
class Events(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.events: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.events.append("start " + tag + " " + repr(attrs))

    def handle_endtag(self, tag: str) -> None:
        self.events.append("end " + tag)

    def handle_data(self, data: str) -> None:
        self.events.append("data " + repr(data))

    def handle_comment(self, data: str) -> None:
        self.events.append("comment " + repr(data))


for doc in ["<!DOCTYPE html><div class=\"row r1\" id=d1><a href='/x?a=1&amp;b=2'>Item &lt;1&gt;</a><br/></div>",
            "<p title=\"café\">été <b>bold</b></p><!-- note -->",
            "<img src=x.png alt = \"a b\" checked/><span>Tom &amp; Jerry</span>"]:
    p = Events()
    p.feed(doc)
    p.close()
    for e in p.events:
        print(e)

# fnmatch's patterns, as a router's rules
for name in ["auth.login.failed", "payments.refund.failed", "http.request.404", "http.request.200x",
             "db.query.slowest", "cache.get.miss", "worker.debug.sync", "gc.collect"]:
    hits = [rule for rule in ["auth.*.failed", "*.failed", "http.request.[45]??", "db.query.slow*", "*.debug.*",
                              "cache.*"] if fnmatch.fnmatchcase(name, rule)]
    print(name, hits)
