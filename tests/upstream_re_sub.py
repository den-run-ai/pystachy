# Adapted from CPython 3.13.16 Lib/test/test_re.py, commit cbc944f4bc59639a444dd971c737788ba2283a91:
# what ReTests checks of sub(), subn(), expand() and their templates, split(), findall() and
# finditer(), and of the progress they make past empty matches (test_basic_re_sub,
# test_bug_449964, test_bug_449000, test_sub_template_numeric_escape, test_qualified_re_sub,
# test_bug_114660, test_symbolic_refs, test_re_subn, test_re_split, test_qualified_re_split,
# test_re_findall, test_bug_117612, test_groupdict, test_expand, test_finditer, test_bug_931848,
# test_bug_817234, test_dollar_matches_twice, test_bug_6509, test_issue17998, test_zerowidth,
# test_bug_34294, test_findall_possessive_quantifiers, test_findall_atomic_grouping,
# test_bug_16688, test_possible_set_operations, test_re_escape_non_ascii, test_large_subn,
# test_bug_581080, test_character_set_any).
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
#
# Each case runs through lib/re, Pystachy's port of re, compiled; this file's .out was recorded
# with CPython's own re. The unittest scaffolding becomes tables of the upstream arguments, and
# each case prints its result: subn()'s string and count, split()'s list, findall()'s list and the
# spans of finditer()'s matches.
#
# EXCLUDED (not in the tables):
# - bytes, bytearray and memoryview patterns, strings and replacements, str subclasses (S, B): the
#   port has str patterns and strs only.
# - test_re_split's "(b)|(:+)" and "(:)*" on ":a:b::c": a group that takes no part in a match puts
#   None in CPython's list, which the port's list[str] cannot hold (a documented deviation:
#   NotImplementedError; issue #242).
# - findall() of a pattern of 2 groups or more (test_re_findall's "(:)(:*)", test_bug_117612,
#   test_bug_34294): CPython's list of tuples has no type in Pystachy (a documented deviation,
#   NotImplementedError; tuple[T, ...] is issue #121); the same matches are checked here through
#   finditer() and m.group(1, 2), which CPython's findall() would give with '' for None.
# - Match.groups() (test_bug_34294's finditer() groups): no type in Pystachy (documented);
#   m.group(1, 2) is printed instead.
# - test_possible_set_operations' patterns that warn (FutureWarning: possible set difference,
#   intersection, union, symmetric difference or nested set): the port has no warnings; its four
#   patterns that do not warn are here.
# - positional count and maxsplit (DeprecationWarning), and the TypeErrors of too many arguments:
#   the keyword forms are here.
# - test_scanner, and test_bug_581080's scanner() and next() of finditer(): the port has no
#   Scanner, and its finditer() returns a list (documented); the finditer() matches are here.
# - test_large_subn on 2**31 characters (bigmem): subn('', '', s) runs on 10**3 characters here
#   (make verify runs this program with a collection at every allocation, gc-stress, where the
#   port's allocation for each of the matches scans the list of the pieces made so far).
import re


def at(s: str, i: int) -> str:
    # a position in s: the index, or in non-ASCII text the text before it (Pystachy's index counts
    # UTF-8 bytes there, a documented deviation, but slices out the same text)
    if i < 0 or s.isascii():
        return str(i)
    return repr(s[:i])


def spans(pattern: str, string: str, flags: int) -> str:
    # the spans of finditer()'s matches, and the groups of each where the pattern has 2 or more
    p = re.compile(pattern, flags)
    out: list[str] = []
    for m in p.finditer(string):
        x = "(%s, %s)" % (at(string, m.start()), at(string, m.end()))
        if p.groups >= 2:
            x += repr([m.group(i) for i in range(1, p.groups + 1)])
        out.append(x)
    return " ".join(out)


SUBS = [
    # test_basic_re_sub
    ('y', 'a', 'xyz', 0), ('\xe0', 'a', 'x\xe0z', 0), ('\u0430', 'a', 'x\u0430z', 0),
    ('\U0001d49c', 'a', 'x\U0001d49cz', 0), ("(?i)b+", "x", "bbbb BBBB", 0), ('.', r"\n", 'x', 0),
    ('(.)', r"\1\1", 'x', 0), ('(.)', r"\\1\\1", 'x', 0), ('(?P<a>x)', r'\g<a>\g<a>', 'xx', 0),
    ('(?P<a>x)', r'\g<a>\g<1>', 'xx', 0), ('(?P<unk>x)', r'\g<unk>\g<unk>', 'xx', 0),
    ('(?P<unk>x)', r'\g<1>\g<1>', 'xx', 0), ('()x', r'\g<0>\g<0>', 'xx', 0), ('a', r'\t\n\v\r\f\a\b', 'a', 0),
    ('a', '\t\n\v\r\f\a\b', 'a', 0), (r'^\s*', 'X', 'test', 0),
    # test_bug_449964
    (r'(?P<unk>x)', r'\g<1>\g<1>\b', 'xx', 0),
    # test_bug_449000
    (r'\r\n', r'\n', 'abc\r\ndef\r\n', 0), ('\r\n', r'\n', 'abc\r\ndef\r\n', 0), (r'\r\n', '\n', 'abc\r\ndef\r\n', 0),
    ('\r\n', '\n', 'abc\r\ndef\r\n', 0),
    # test_sub_template_numeric_escape
    ('x', r'\0', 'x', 0), ('x', r'\000', 'x', 0), ('x', r'\001', 'x', 0), ('x', r'\008', 'x', 0),
    ('x', r'\009', 'x', 0), ('x', r'\111', 'x', 0), ('x', r'\117', 'x', 0), ('x', r'\377', 'x', 0),
    ('x', r'\1111', 'x', 0), ('x', r'\00', 'x', 0), ('x', r'\07', 'x', 0), ('x', r'\08', 'x', 0),
    ('x', r'\09', 'x', 0), ('x', r'\0a', 'x', 0), ('(((((((((((x)))))))))))', r'\11', 'x', 0),
    ('((((((((((y))))))))))(.)', r'\118', 'xyz', 0), ('((((((((((y))))))))))(.)', r'\11a', 'xyz', 0),
    # test_qualified_re_sub
    ('a', 'b', 'aaaaa', 0), ('a', 'b', 'aaaaa', 1),
    # test_bug_114660
    (r'(\S)\s+(\S)', r'\1 \2', 'hello  there', 0),
    # test_symbolic_refs
    ('(?P<a>x)|(?P<b>y)', r'\g<b>', 'xx', 0), ('(?P<a>x)|(?P<b>y)', r'\2', 'xx', 0), ('(?P<µ>x)', r'\g<µ>', 'xx', 0),
    ('(?P<𝔘𝔫𝔦𝔠𝔬𝔡𝔢>x)', r'\g<𝔘𝔫𝔦𝔠𝔬𝔡𝔢>', 'xx', 0),
    # test_re_subn
    ("(?i)b+", "x", "bbbb BBBB", 0), ("b+", "x", "bbbb BBBB", 0), ("b+", "x", "xyz", 0), ("b*", "x", "xyz", 0),
    ("b*", "x", "xyz", 2),
    # test_dollar_matches_twice
    ('$', '#', 'a\nb\n', 0), ('$', '#', 'a\nb\nc', 0), ('$', '#', '\n', 0), ('(?m)$', '#', 'a\nb\n', 0),
    ('(?m)$', '#', 'a\nb\nc', 0), ('(?m)$', '#', '\n', 0),
    # test_bug_6509
    (r'a(\w)', 'b\\1', 'ac', 0), ('a(.)', 'b\\1', 'a\u1234', 0),
    # test_zerowidth
    (r"\b", "-", "a::bc", 0), (r"\b|:+", "-", "a::bc", 0), (r"(\b|:+)", r"[\1]", "a::bc", 0),
]
for pattern, repl, string, count in SUBS:
    print("subn", repr(pattern), repr(repl), repr(string), count, re.subn(pattern, repl, string, count=count))


def bump_num(matchobj: re.Match) -> str:
    int_value = int(str(matchobj.group(0)))
    return str(int_value + 1)


# test_basic_re_sub: a function as the replacement (its str is taken as it is)
print(re.sub(r'\d+', bump_num, '08.2 -2 23x99y'), re.sub(r'\d+', bump_num, '08.2 -2 23x99y', count=3))
print(repr(re.sub('.', lambda m: r"\n", 'x')), repr(re.sub('(.)', lambda m: r"\1\1", 'x')))
# test_bug_6509
print(re.compile('..').sub(lambda m: 'str', 'a5'))
# test_symbolic_refs: more than 100 groups
pat200 = '|'.join(['x(?P<a%d>%x)y' % (i, i) for i in range(1, 200 + 1)])
print(re.sub(pat200, r'\g<200>', 'xc8yzxc8y'))
# test_large_subn (on 10**3 characters, not 2**31): an empty match at each of them, and at the end
s = 'a' * 10**3
r, n = re.subn('', '', s)
print(r == s, n)

# test_groupdict, test_expand
m = re.match('(?P<first>first) (?P<second>second)', 'first second')
assert m is not None
print(m.groupdict(), m.expand(r"\2 \1 \g<second> \g<first>"))
m = re.match("(?P<first>first)|(?P<second>second)", "first")
assert m is not None
print(m.groupdict(), m.groupdict("-"), repr(m.expand(r"\2 \g<second>")))

SPLITS = [
    # test_re_split
    (":", ":a:b::c", 0), (":+", ":a:b::c", 0), ("(:+)", ":a:b::c", 0),
    (":", ":\xe0:\xdf::\xe7", 0), (":+", ":\xe0:\xdf::\xe7", 0), ("(:+)", ":\xe0:\xdf::\xe7", 0),
    (":", ":\u0430:\u0431::\u0432", 0), ("(:+)", ":\u0430:\u0431::\u0432", 0),
    (":", ":\U0001d49c:\U0001d49e::\U0001d4b5", 0), ("(:+)", ":\U0001d49c:\U0001d49e::\U0001d4b5", 0),
    ("(?::+)", ":a:b::c", 0), ("(:)+", ":a:b::c", 0), ("([b:]+)", ":a:b::c", 0), ("(?:b)|(?::+)", ":a:b::c", 0),
    (':*', ':a:b::c', 0), ('(?::*)', ':a:b::c', 0), ('(:*)', ':a:b::c', 0), ('', ':a:b::c', 0), (r'\b', ':a:b::c', 0),
    (r'(?=:)', ':a:b::c', 0), (r'(?<=:)', ':a:b::c', 0),
    # test_qualified_re_split
    (":", ":a:b::c", 2), (':', 'a:b:c:d', 2), ("(:)", ":a:b::c", 2), ("(:+)", ":a:b::c", 2), ("(:*)", ":a:b::c", 2),
    # test_bug_931848
    ("[\u002E\u3002\uFF0E\uFF61]", "a.b.c", 0), ("[\u002E\u3002\uFF0E\uFF61]", "a\u3002b\uff0ec\uff61", 0),
    # test_zerowidth
    (r"\b", "a::bc", 0), (r"\b|:+", "a::bc", 0), (r"(?<!\w)(?=\w)|:+", "a::bc", 0), (r"(?<=\w)(?!\w)|:+", "a::bc", 0),
]
for pattern, string, maxsplit in SPLITS:
    print("split", repr(pattern), repr(string), maxsplit, re.split(pattern, string, maxsplit=maxsplit))

# test_possible_set_operations' patterns that do not warn, on the ASCII characters
ascii128 = ''.join(["%c" % i for i in range(128)])
FINDALLS = [
    (r'[--1]', ascii128, 0), (r'[&&1]', ascii128, 0), (r'[||1]', ascii128, 0), (r'[~~1]', ascii128, 0),
    # test_re_findall
    (":+", "abc", 0), (":+", "a:b::c:::d", 0), ("(:+)", "a:b::c:::d", 0), ("(:)(:*)", "a:b::c:::d", 0),
    ("\xe0+", "a\xe0b\xe0\xe0c\xe0\xe0\xe0d", 0), ("(\xe0+)", "a\xe0b\xe0\xe0c\xe0\xe0\xe0d", 0),
    ("(\xe0)(\xe0*)", "a\xe0b\xe0\xe0c\xe0\xe0\xe0d", 0), ("\u0430+", "a\u0430b\u0430\u0430c\u0430\u0430\u0430d", 0),
    ("(\u0430)(\u0430*)", "a\u0430b\u0430\u0430c\u0430\u0430\u0430d", 0),
    ("\U0001d49c+", "a\U0001d49cb\U0001d49c\U0001d49cc\U0001d49c\U0001d49c\U0001d49cd", 0),
    ("(\U0001d49c)(\U0001d49c*)", "a\U0001d49cb\U0001d49c\U0001d49cc\U0001d49c\U0001d49c\U0001d49cd", 0),
    # test_bug_117612
    (r"(a|(b))", "aba", 0),
    # test_finditer
    (r":+", "a:b::c:::d", 0),
    # test_bug_817234, test_bug_581080
    (r".*", "asdf", 0), (r"\s", "a b", 0),
    # test_issue17998
    ('.*yz', 'xyz', re.S), ('.*?yz', 'xyz', re.S), ('.+yz', 'xyz', re.S), ('.+?yz', 'xyz', re.S),
    ('.?yz', 'xyz', re.S), ('.??yz', 'xyz', re.S), ('.{1}yz', 'xyz', re.S), ('.{1}?yz', 'xyz', re.S),
    # test_zerowidth
    (r"\b|:+", "a::bc", 0), (r"\b|\w+", "a::bc", 0),
    # test_bug_34294
    (r"(?=(.)(.)?)", "ab", 0), (r"(?=<(?P<tag>\w+)/?>(?:(?P<text>.+?)</(?P=tag)>)?)", "<test><foo2/></test>", 0),
    (r"(?=<(?P<tag>\w+)/?>(?:(?P<text>.+?)</(?P=tag)>)?)", "<test>Hello</test><foo/>", 0),
    (r"(?=<(?P<tag>\w+)/?>(?:(?P<text>.+?)</(?P=tag)>)?)", "<test>Hello</test><foo/><foo/>", 0),
    # test_findall_possessive_quantifiers
    (r'a++', 'aab', 0), (r'a*+', 'aab', 0), (r'a?+', 'aab', 0), (r'a{1,3}+', 'aab', 0), (r'(?:ab)++', 'ababc', 0),
    (r'(?:ab)*+', 'ababc', 0), (r'(?:ab)?+', 'ababc', 0), (r'(?:ab){1,3}+', 'ababc', 0),
    # test_findall_atomic_grouping
    (r'(?>a+)', 'aab', 0), (r'(?>a*)', 'aab', 0), (r'(?>a?)', 'aab', 0), (r'(?>a{1,3})', 'aab', 0),
    (r'(?>(?:ab)+)', 'ababc', 0), (r'(?>(?:ab)*)', 'ababc', 0), (r'(?>(?:ab)?)', 'ababc', 0),
    (r'(?>(?:ab){1,3})', 'ababc', 0),
    # test_bug_16688
    (r"(?i)(a)\1", "aa \u0100", 0), (r"(?s).{1,3}", "\u0100\u0100", 0),
    # test_character_set_any
    (r'[\s\S]', '1x\n', 0), (r'[\d\D]', '1x\n', 0), (r'[\w\W]', '1x\n', 0), (r'[\S\s]', '1x\n', 0), (r'\s|\S', '1x\n', 0),
]
for pattern, string, flags in FINDALLS:
    p = re.compile(pattern, flags)
    found = repr(p.findall(string)) if p.groups < 2 else "(%d groups)" % p.groups
    print("findall", repr(pattern), repr(string) if len(string) < 40 else "ascii128", int(flags), found, "|", spans(pattern, string, flags))

# test_bug_34294: groupdict() of each finditer() match
p = re.compile(r"(?=<(?P<tag>\w+)/?>(?:(?P<text>.+?)</(?P=tag)>)?)")
for s in ["<test><foo2/></test>", "<test>Hello</test><foo/>", "<test>Hello</test><foo/><foo/>"]:
    print([mm.groupdict() for mm in p.finditer(s)])

# test_finditer: pos and endpos, also as keywords
pat = re.compile(r":+")
print([item.group(0) for item in pat.finditer("a:b::c:::d", 1, 10)], [item.group(0) for item in pat.finditer("a:b::c:::d", pos=1, endpos=10)],
      [item.group(0) for item in pat.finditer("a:b::c:::d", endpos=10, pos=1)], [item.group(0) for item in pat.finditer("a:b::c:::d", pos=3, endpos=8)])

# test_re_escape_non_ascii
s = 'xxx\u2620\u2620\u2620xxx'
s_escaped = re.escape(s)
print(s_escaped == s, re.fullmatch(s_escaped, s) is not None)
m = re.search('.%s+.' % re.escape('\u2620'), s)
assert m is not None
print(m.group(), at(s, m.start()), at(s, m.end()))
