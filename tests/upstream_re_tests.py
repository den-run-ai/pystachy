# Adapted from CPython 3.13.16 Lib/test/re_tests.py (its benchmarks table, and its tests table up
# to "All tests from Perl", which tests/upstream_re_tests_perl.py runs from there on) and
# Lib/test/test_re.py (ExternalTests.test_re_tests and test_re_benchmarks, which run them), commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
#
# Every case runs through lib/re, Pystachy's port of re, compiled; this file's .out was recorded
# with CPython's own re. The tables are re_tests.py's, with its comments; the edits are mechanical:
# a 3-tuple (pattern, string, outcome) has '' and '' for its expression and expected value (a
# Pystachy list holds one tuple type), chr(255) and chr(254) are written '\xff' and '\xfe' (chr()
# of i < 256 is a byte in Pystachy, docs/language.md), and "[SUCCEED, FAIL, SYNTAX_ERROR] =
# range(3)" binds the three names one by one. test_re_tests's eval() of a case's expression in its
# dict of groups becomes value() below (an expression is "+" of found, gN, a group's name and str
# literals). Each case prints the match (its span, each group's value and span, lastindex and
# lastgroup) and the expression's value, which it asserts as upstream does, then the subtests'
# searches: within the match's span plus one ("range"), with IGNORECASE ("I") and with UNICODE
# ("U"), "=" where one gives the case's own match.
#
# EXCLUDED: test_re_tests's "bytes pattern match" and "locale-sensitive match" subtests (bytes
# patterns, and LOCALE, which only they take): the port has str patterns only. test_re_benchmarks
# pads each string with 1,000 spaces on each side, not 10,000: make verify runs this program with
# a collection at every allocation (gc-stress), and each backtracking step over the padding
# allocates.
import re

# The 3 possible outcomes for each pattern
SUCCEED, FAIL, SYNTAX_ERROR = 0, 1, 2

benchmarks = [

    # test common prefix
    ('Python|Perl', 'Perl'),    # Alternation
    ('(Python|Perl)', 'Perl'),  # Grouped alternation

    ('Python|Perl|Tcl', 'Perl'),        # Alternation
    ('(Python|Perl|Tcl)', 'Perl'),      # Grouped alternation

    ('(Python)\\1', 'PythonPython'),    # Backreference
    ('([0a-z][a-z0-9]*,)+', 'a5,b7,c9,'), # Disable the fastmap optimization
    ('([a-z][a-z0-9]*,)+', 'a5,b7,c9,'), # A few sets

    ('Python', 'Python'),               # Simple text literal
    ('.*Python', 'Python'),             # Bad text literal
    ('.*Python.*', 'Python'),           # Worse text literal
    ('.*(Python)', 'Python'),           # Bad text literal with grouping

]

tests = [
    # Test ?P< and ?P= extensions
    ('(?P<foo_123', '', SYNTAX_ERROR, '', ''),      # Unterminated group identifier
    ('(?P<1>a)', '', SYNTAX_ERROR, '', ''),         # Begins with a digit
    ('(?P<!>a)', '', SYNTAX_ERROR, '', ''),         # Begins with an illegal char
    ('(?P<foo!>a)', '', SYNTAX_ERROR, '', ''),      # Begins with an illegal char

    # Same tests, for the ?P= form
    ('(?P<foo_123>a)(?P=foo_123', 'aa', SYNTAX_ERROR, '', ''),
    ('(?P<foo_123>a)(?P=1)', 'aa', SYNTAX_ERROR, '', ''),
    ('(?P<foo_123>a)(?P=!)', 'aa', SYNTAX_ERROR, '', ''),
    ('(?P<foo_123>a)(?P=foo_124', 'aa', SYNTAX_ERROR, '', ''),  # Backref to undefined group

    ('(?P<foo_123>a)', 'a', SUCCEED, 'g1', 'a'),
    ('(?P<foo_123>a)(?P=foo_123)', 'aa', SUCCEED, 'g1', 'a'),

    # Test octal escapes
    ('\\1', 'a', SYNTAX_ERROR, '', ''),    # Backreference
    ('[\\1]', '\1', SUCCEED, 'found', '\1'),  # Character
    ('\\09', chr(0) + '9', SUCCEED, 'found', chr(0) + '9'),
    ('\\141', 'a', SUCCEED, 'found', 'a'),
    ('(a)(b)(c)(d)(e)(f)(g)(h)(i)(j)(k)(l)\\119', 'abcdefghijklk9', SUCCEED, 'found+"-"+g11', 'abcdefghijklk9-k'),

    # Test \0 is handled everywhere
    (r'\0', '\0', SUCCEED, 'found', '\0'),
    (r'[\0a]', '\0', SUCCEED, 'found', '\0'),
    (r'[a\0]', '\0', SUCCEED, 'found', '\0'),
    (r'[^a\0]', '\0', FAIL, '', ''),

    # Test various letter escapes
    (r'\a[\b]\f\n\r\t\v', '\a\b\f\n\r\t\v', SUCCEED, 'found', '\a\b\f\n\r\t\v'),
    (r'[\a][\b][\f][\n][\r][\t][\v]', '\a\b\f\n\r\t\v', SUCCEED, 'found', '\a\b\f\n\r\t\v'),
    # NOTE: not an error under PCRE/PRE:
    (r'\u', '', SYNTAX_ERROR, '', ''),    # A Perl escape
    # (r'\c\e\g\h\i\j\k\m\o\p\q\y\z', 'ceghijkmopqyz', SUCCEED, 'found', 'ceghijkmopqyz'),
    # new \x semantics
    (r'\x00ffffffffffffff', '\377', FAIL, 'found', '\xff'),
    (r'\x00f', '\017', FAIL, 'found', chr(15)),
    (r'\x00fe', '\376', FAIL, 'found', '\xfe'),
    # (r'\x00ffffffffffffff', '\377', SUCCEED, 'found', '\xff'),
    # (r'\x00f', '\017', SUCCEED, 'found', chr(15)),
    # (r'\x00fe', '\376', SUCCEED, 'found', '\xfe'),

    (r"^\w+=(\\[\000-\277]|[^\n\\])*", "SRC=eval.c g.c blah blah blah \\\\\n\tapes.c",
     SUCCEED, 'found', "SRC=eval.c g.c blah blah blah \\\\"),

    # Test that . only matches \n in DOTALL mode
    ('a.b', 'acb', SUCCEED, 'found', 'acb'),
    ('a.b', 'a\nb', FAIL, '', ''),
    ('a.*b', 'acc\nccb', FAIL, '', ''),
    ('a.{4,5}b', 'acc\nccb', FAIL, '', ''),
    ('a.b', 'a\rb', SUCCEED, 'found', 'a\rb'),
    ('(?s)a.b', 'a\nb', SUCCEED, 'found', 'a\nb'),
    ('(?s)a.*b', 'acc\nccb', SUCCEED, 'found', 'acc\nccb'),
    ('(?s)a.{4,5}b', 'acc\nccb', SUCCEED, 'found', 'acc\nccb'),
    ('(?s)a.b', 'a\rb', SUCCEED, 'found', 'a\rb'),

    (')', '', SYNTAX_ERROR, '', ''),           # Unmatched right bracket
    ('', '', SUCCEED, 'found', ''),    # Empty pattern
    ('abc', 'abc', SUCCEED, 'found', 'abc'),
    ('abc', 'xbc', FAIL, '', ''),
    ('abc', 'axc', FAIL, '', ''),
    ('abc', 'abx', FAIL, '', ''),
    ('abc', 'xabcy', SUCCEED, 'found', 'abc'),
    ('abc', 'ababc', SUCCEED, 'found', 'abc'),
    ('ab*c', 'abc', SUCCEED, 'found', 'abc'),
    ('ab*bc', 'abc', SUCCEED, 'found', 'abc'),
    ('ab*bc', 'abbc', SUCCEED, 'found', 'abbc'),
    ('ab*bc', 'abbbbc', SUCCEED, 'found', 'abbbbc'),
    ('ab+bc', 'abbc', SUCCEED, 'found', 'abbc'),
    ('ab+bc', 'abc', FAIL, '', ''),
    ('ab+bc', 'abq', FAIL, '', ''),
    ('ab+bc', 'abbbbc', SUCCEED, 'found', 'abbbbc'),
    ('ab?bc', 'abbc', SUCCEED, 'found', 'abbc'),
    ('ab?bc', 'abc', SUCCEED, 'found', 'abc'),
    ('ab?bc', 'abbbbc', FAIL, '', ''),
    ('ab?c', 'abc', SUCCEED, 'found', 'abc'),
    ('^abc$', 'abc', SUCCEED, 'found', 'abc'),
    ('^abc$', 'abcc', FAIL, '', ''),
    ('^abc', 'abcc', SUCCEED, 'found', 'abc'),
    ('^abc$', 'aabc', FAIL, '', ''),
    ('abc$', 'aabc', SUCCEED, 'found', 'abc'),
    ('^', 'abc', SUCCEED, 'found+"-"', '-'),
    ('$', 'abc', SUCCEED, 'found+"-"', '-'),
    ('a.c', 'abc', SUCCEED, 'found', 'abc'),
    ('a.c', 'axc', SUCCEED, 'found', 'axc'),
    ('a.*c', 'axyzc', SUCCEED, 'found', 'axyzc'),
    ('a.*c', 'axyzd', FAIL, '', ''),
    ('a[bc]d', 'abc', FAIL, '', ''),
    ('a[bc]d', 'abd', SUCCEED, 'found', 'abd'),
    ('a[b-d]e', 'abd', FAIL, '', ''),
    ('a[b-d]e', 'ace', SUCCEED, 'found', 'ace'),
    ('a[b-d]', 'aac', SUCCEED, 'found', 'ac'),
    ('a[-b]', 'a-', SUCCEED, 'found', 'a-'),
    ('a[\\-b]', 'a-', SUCCEED, 'found', 'a-'),
    # NOTE: not an error under PCRE/PRE:
    # ('a[b-]', 'a-', SYNTAX_ERROR, '', ''),
    ('a[]b', '-', SYNTAX_ERROR, '', ''),
    ('a[', '-', SYNTAX_ERROR, '', ''),
    ('a\\', '-', SYNTAX_ERROR, '', ''),
    ('abc)', '-', SYNTAX_ERROR, '', ''),
    ('(abc', '-', SYNTAX_ERROR, '', ''),
    ('a]', 'a]', SUCCEED, 'found', 'a]'),
    ('a[]]b', 'a]b', SUCCEED, 'found', 'a]b'),
    ('a[\\]]b', 'a]b', SUCCEED, 'found', 'a]b'),
    ('a[^bc]d', 'aed', SUCCEED, 'found', 'aed'),
    ('a[^bc]d', 'abd', FAIL, '', ''),
    ('a[^-b]c', 'adc', SUCCEED, 'found', 'adc'),
    ('a[^-b]c', 'a-c', FAIL, '', ''),
    ('a[^]b]c', 'a]c', FAIL, '', ''),
    ('a[^]b]c', 'adc', SUCCEED, 'found', 'adc'),
    ('\\ba\\b', 'a-', SUCCEED, '"-"', '-'),
    ('\\ba\\b', '-a', SUCCEED, '"-"', '-'),
    ('\\ba\\b', '-a-', SUCCEED, '"-"', '-'),
    ('\\by\\b', 'xy', FAIL, '', ''),
    ('\\by\\b', 'yz', FAIL, '', ''),
    ('\\by\\b', 'xyz', FAIL, '', ''),
    ('x\\b', 'xyz', FAIL, '', ''),
    ('x\\B', 'xyz', SUCCEED, '"-"', '-'),
    ('\\Bz', 'xyz', SUCCEED, '"-"', '-'),
    ('z\\B', 'xyz', FAIL, '', ''),
    ('\\Bx', 'xyz', FAIL, '', ''),
    ('\\Ba\\B', 'a-', FAIL, '"-"', '-'),
    ('\\Ba\\B', '-a', FAIL, '"-"', '-'),
    ('\\Ba\\B', '-a-', FAIL, '"-"', '-'),
    ('\\By\\B', 'xy', FAIL, '', ''),
    ('\\By\\B', 'yz', FAIL, '', ''),
    ('\\By\\b', 'xy', SUCCEED, '"-"', '-'),
    ('\\by\\B', 'yz', SUCCEED, '"-"', '-'),
    ('\\By\\B', 'xyz', SUCCEED, '"-"', '-'),
    ('ab|cd', 'abc', SUCCEED, 'found', 'ab'),
    ('ab|cd', 'abcd', SUCCEED, 'found', 'ab'),
    ('()ef', 'def', SUCCEED, 'found+"-"+g1', 'ef-'),
    ('$b', 'b', FAIL, '', ''),
    ('a\\(b', 'a(b', SUCCEED, 'found+"-"+g1', 'a(b-Error'),
    ('a\\(*b', 'ab', SUCCEED, 'found', 'ab'),
    ('a\\(*b', 'a((b', SUCCEED, 'found', 'a((b'),
    ('a\\\\b', 'a\\b', SUCCEED, 'found', 'a\\b'),
    ('((a))', 'abc', SUCCEED, 'found+"-"+g1+"-"+g2', 'a-a-a'),
    ('(a)b(c)', 'abc', SUCCEED, 'found+"-"+g1+"-"+g2', 'abc-a-c'),
    ('a+b+c', 'aabbabc', SUCCEED, 'found', 'abc'),
    ('(a+|b)*', 'ab', SUCCEED, 'found+"-"+g1', 'ab-b'),
    ('(a+|b)+', 'ab', SUCCEED, 'found+"-"+g1', 'ab-b'),
    ('(a+|b)?', 'ab', SUCCEED, 'found+"-"+g1', 'a-a'),
    (')(', '-', SYNTAX_ERROR, '', ''),
    ('[^ab]*', 'cde', SUCCEED, 'found', 'cde'),
    ('abc', '', FAIL, '', ''),
    ('a*', '', SUCCEED, 'found', ''),
    ('a|b|c|d|e', 'e', SUCCEED, 'found', 'e'),
    ('(a|b|c|d|e)f', 'ef', SUCCEED, 'found+"-"+g1', 'ef-e'),
    ('abcd*efg', 'abcdefg', SUCCEED, 'found', 'abcdefg'),
    ('ab*', 'xabyabbbz', SUCCEED, 'found', 'ab'),
    ('ab*', 'xayabbbz', SUCCEED, 'found', 'a'),
    ('(ab|cd)e', 'abcde', SUCCEED, 'found+"-"+g1', 'cde-cd'),
    ('[abhgefdc]ij', 'hij', SUCCEED, 'found', 'hij'),
    ('^(ab|cd)e', 'abcde', FAIL, 'xg1y', 'xy'),
    ('(abc|)ef', 'abcdef', SUCCEED, 'found+"-"+g1', 'ef-'),
    ('(a|b)c*d', 'abcd', SUCCEED, 'found+"-"+g1', 'bcd-b'),
    ('(ab|ab*)bc', 'abc', SUCCEED, 'found+"-"+g1', 'abc-a'),
    ('a([bc]*)c*', 'abc', SUCCEED, 'found+"-"+g1', 'abc-bc'),
    ('a([bc]*)(c*d)', 'abcd', SUCCEED, 'found+"-"+g1+"-"+g2', 'abcd-bc-d'),
    ('a([bc]+)(c*d)', 'abcd', SUCCEED, 'found+"-"+g1+"-"+g2', 'abcd-bc-d'),
    ('a([bc]*)(c+d)', 'abcd', SUCCEED, 'found+"-"+g1+"-"+g2', 'abcd-b-cd'),
    ('a[bcd]*dcdcde', 'adcdcde', SUCCEED, 'found', 'adcdcde'),
    ('a[bcd]+dcdcde', 'adcdcde', FAIL, '', ''),
    ('(ab|a)b*c', 'abc', SUCCEED, 'found+"-"+g1', 'abc-ab'),
    ('((a)(b)c)(d)', 'abcd', SUCCEED, 'g1+"-"+g2+"-"+g3+"-"+g4', 'abc-a-b-d'),
    ('[a-zA-Z_][a-zA-Z0-9_]*', 'alpha', SUCCEED, 'found', 'alpha'),
    ('^a(bc+|b[eh])g|.h$', 'abh', SUCCEED, 'found+"-"+g1', 'bh-None'),
    ('(bc+d$|ef*g.|h?i(j|k))', 'effgz', SUCCEED, 'found+"-"+g1+"-"+g2', 'effgz-effgz-None'),
    ('(bc+d$|ef*g.|h?i(j|k))', 'ij', SUCCEED, 'found+"-"+g1+"-"+g2', 'ij-ij-j'),
    ('(bc+d$|ef*g.|h?i(j|k))', 'effg', FAIL, '', ''),
    ('(bc+d$|ef*g.|h?i(j|k))', 'bcdd', FAIL, '', ''),
    ('(bc+d$|ef*g.|h?i(j|k))', 'reffgz', SUCCEED, 'found+"-"+g1+"-"+g2', 'effgz-effgz-None'),
    ('(((((((((a)))))))))', 'a', SUCCEED, 'found', 'a'),
    ('multiple words of text', 'uh-uh', FAIL, '', ''),
    ('multiple words', 'multiple words, yeah', SUCCEED, 'found', 'multiple words'),
    ('(.*)c(.*)', 'abcde', SUCCEED, 'found+"-"+g1+"-"+g2', 'abcde-ab-de'),
    ('\\((.*), (.*)\\)', '(a, b)', SUCCEED, 'g2+"-"+g1', 'b-a'),
    ('[k]', 'ab', FAIL, '', ''),
    ('a[-]?c', 'ac', SUCCEED, 'found', 'ac'),
    ('(abc)\\1', 'abcabc', SUCCEED, 'g1', 'abc'),
    ('([a-c]*)\\1', 'abcabc', SUCCEED, 'g1', 'abc'),
    ('^(.+)?B', 'AB', SUCCEED, 'g1', 'A'),
    ('(a+).\\1$', 'aaaaa', SUCCEED, 'found+"-"+g1', 'aaaaa-aa'),
    ('^(a+).\\1$', 'aaaa', FAIL, '', ''),
    ('(abc)\\1', 'abcabc', SUCCEED, 'found+"-"+g1', 'abcabc-abc'),
    ('([a-c]+)\\1', 'abcabc', SUCCEED, 'found+"-"+g1', 'abcabc-abc'),
    ('(a)\\1', 'aa', SUCCEED, 'found+"-"+g1', 'aa-a'),
    ('(a+)\\1', 'aa', SUCCEED, 'found+"-"+g1', 'aa-a'),
    ('(a+)+\\1', 'aa', SUCCEED, 'found+"-"+g1', 'aa-a'),
    ('(a).+\\1', 'aba', SUCCEED, 'found+"-"+g1', 'aba-a'),
    ('(a)ba*\\1', 'aba', SUCCEED, 'found+"-"+g1', 'aba-a'),
    ('(aa|a)a\\1$', 'aaa', SUCCEED, 'found+"-"+g1', 'aaa-a'),
    ('(a|aa)a\\1$', 'aaa', SUCCEED, 'found+"-"+g1', 'aaa-a'),
    ('(a+)a\\1$', 'aaa', SUCCEED, 'found+"-"+g1', 'aaa-a'),
    ('([abc]*)\\1', 'abcabc', SUCCEED, 'found+"-"+g1', 'abcabc-abc'),
    ('(a)(b)c|ab', 'ab', SUCCEED, 'found+"-"+g1+"-"+g2', 'ab-None-None'),
    ('(a)+x', 'aaax', SUCCEED, 'found+"-"+g1', 'aaax-a'),
    ('([ac])+x', 'aacx', SUCCEED, 'found+"-"+g1', 'aacx-c'),
    ('([^/]*/)*sub1/', 'd:msgs/tdir/sub1/trial/away.cpp', SUCCEED, 'found+"-"+g1', 'd:msgs/tdir/sub1/-tdir/'),
    ('([^.]*)\\.([^:]*):[T ]+(.*)', 'track1.title:TBlah blah blah', SUCCEED, 'found+"-"+g1+"-"+g2+"-"+g3', 'track1.title:TBlah blah blah-track1-title-Blah blah blah'),
    ('([^N]*N)+', 'abNNxyzN', SUCCEED, 'found+"-"+g1', 'abNNxyzN-xyzN'),
    ('([^N]*N)+', 'abNNxyz', SUCCEED, 'found+"-"+g1', 'abNN-N'),
    ('([abc]*)x', 'abcx', SUCCEED, 'found+"-"+g1', 'abcx-abc'),
    ('([abc]*)x', 'abc', FAIL, '', ''),
    ('([xyz]*)x', 'abcx', SUCCEED, 'found+"-"+g1', 'x-'),
    ('(a)+b|aac', 'aac', SUCCEED, 'found+"-"+g1', 'aac-None'),

    # Test symbolic groups

    ('(?P<i d>aaa)a', 'aaaa', SYNTAX_ERROR, '', ''),
    ('(?P<id>aaa)a', 'aaaa', SUCCEED, 'found+"-"+id', 'aaaa-aaa'),
    ('(?P<id>aa)(?P=id)', 'aaaa', SUCCEED, 'found+"-"+id', 'aaaa-aa'),
    ('(?P<id>aa)(?P=xd)', 'aaaa', SYNTAX_ERROR, '', ''),

    # Test octal escapes/memory references

    ('\\1', 'a', SYNTAX_ERROR, '', ''),
]


def at(s: str, i: int) -> str:
    # a position in s: the index, or in non-ASCII text the text before it (Pystachy's index counts
    # UTF-8 bytes there, a documented deviation, but slices out the same text)
    if i < 0 or s.isascii():
        return str(i)
    return repr(s[:i])


def show(m) -> str:
    # a match: its span, its groups' values and spans, lastindex and lastgroup
    if m is None:
        return "None"
    s = m.string
    out = "(%s, %s)" % (at(s, m.start()), at(s, m.end()))
    if m.re.groups > 0:
        values: list[str | None] = []
        spans: list[str] = []
        for i in range(1, m.re.groups + 1):
            values.append(m.group(i))
            spans.append("(%s, %s)" % (at(s, m.start(i)), at(s, m.end(i))))
        out += " %r %s last=%s/%s" % (values, " ".join(spans), m.lastindex, m.lastgroup)
    return out


def value(m, term: str) -> str:
    # one operand of a case's expression, as test_re_tests's eval() of it in its dict gives it:
    # found, gN (the string 'None' where the group took no part, 'Error' past the last group), a
    # group's name, or a str literal
    term = term.strip()
    if term.startswith('"'):
        return term[1:-1]
    g: str | None = None
    try:
        if term == "found":
            g = m.group(0)
        elif term.startswith("g") and term[1:].isdigit():
            g = m.group(int(term[1:]))
        else:
            g = m.group(term)
    except IndexError:
        return "Error"
    if g is None:
        return "None"
    return g


# ExternalTests.test_re_tests
n = 0
for pattern, s, outcome, repl, expected in tests:
    n += 1
    try:
        obj = re.compile(pattern)
    except re.error as e:
        print(n, repr(pattern), "error:", e)
        assert outcome == SYNTAX_ERROR, "compiled incorrectly"
        continue
    assert outcome != SYNTAX_ERROR, "compiled incorrectly"
    result = obj.search(s)
    main = show(result)
    line = "%d %r %r %s" % (n, pattern, s, main)
    if outcome == FAIL:
        assert result is None, "Succeeded incorrectly"
    else:
        assert result is not None, "Failed incorrectly"
    if result is not None and repl != "":
        # (an expression of a FAIL case that matched, which upstream does not evaluate)
        got = "".join([value(result, term) for term in repl.split("+")])
        line += " | %s=%r" % (repl, got)
        if outcome == SUCCEED:
            assert got == expected, "grouping error"
    variants: list[tuple[str, str]] = []
    if result is not None and pattern[:2] != r"\B" and pattern[-2:] != r"\B" and s.isascii():
        variants.append(("range", show(obj.search(s, result.start(), result.end() + 1))))
    variants.append(("I", show(re.compile(pattern, re.IGNORECASE).search(s))))
    variants.append(("U", show(re.compile(pattern, re.UNICODE).search(s))))
    for tag, v in variants:
        line += " | %s %s" % (tag, "=" if v == main else v)
        if outcome == SUCCEED:
            assert v != "None", tag
    print(line)

# ExternalTests.test_re_benchmarks: each pattern searches, matches and fullmatches its string,
# alone and inside 1,000 spaces on each side (upstream: 10,000)
for pattern, s in benchmarks:
    p = re.compile(pattern)
    s2 = " " * 1000 + s + " " * 1000
    print(repr(pattern), repr(s), show(p.search(s)), "|", show(p.match(s)), "|", show(p.fullmatch(s)), "|", show(p.search(s2)),
          "|", show(p.match(s2, 1000)), "|", show(p.match(s2, 1000, 1000 + len(s))), "|",
          show(p.fullmatch(s2, 1000, 1000 + len(s))))
