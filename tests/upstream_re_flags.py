# Adapted from CPython 3.13.16 Lib/test/test_re.py, commit cbc944f4bc59639a444dd971c737788ba2283a91:
# what ReTests and PatternReprTests check of the flags, case-insensitive matching, escapes,
# categories, word boundaries and Unicode text, and of the Pattern and Match objects
# (test_flags, test_constants, test_ignore_case, test_ignore_case_set, test_ignore_case_range,
# test_inline_flags, test_scoped_flags, test_ignore_spaces, test_comments,
# test_ascii_and_unicode_flag, test_special_escapes, test_other_escapes, test_word_boundaries,
# test_anyall, test_bug_6561, test_search_dot_unicode, test_category, test_not_literal,
# test_search_coverage, test_re_escape, test_sre_character_literals,
# test_sre_character_class_literals, test_bigcharset, test_bug_612074, test_bug_20998,
# test_getattr, test_compile, test_pattern_compare, test_match_repr and PatternReprTests).
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
#
# Each case runs through lib/re, Pystachy's port of re, compiled; this file's .out was recorded
# with CPython's own re. The unittest scaffolding becomes a table of (function, pattern, string,
# flags) cases, each printing its match (span and groups), a superset of what upstream asserts.
# A character upstream makes with chr(i) is made with "%c" % i: chr(i) of i < 256 is a byte in
# Pystachy (docs/language.md); a flag is printed as an int.
#
# EXCLUDED (not in the tables):
# - bytes patterns and subjects, LOCALE (only for bytes patterns): test_locale_*,
#   test_re_escape_bytes, test_re_escape_non_ascii_bytes, test_sre_byte_literals,
#   test_sre_byte_class_literals, test_bug_926075 and test_bug_29444 (a bytearray changed under a
#   match), and the bytes halves of the tests here: the port has str patterns only.
# - test_named_unicode_escapes' matches (\N{LESS-THAN SIGN}, ...): the port has no table of the
#   character names (a documented deviation); its errors are in upstream_re_errors.py.
# - test_flags_repr and test_enum (str(re.A)): the flags are ints, not RegexFlag members (a
#   documented deviation).
# - PatternReprTests.test_bytes and test_locale: bytes patterns.
# - test_getattr's m.regs and groupindex's immutability (a dict in the port, a mappingproxy in
#   CPython): documented deviations.
# - test_pattern_compare's pattern1 < pattern2 (TypeError) and hash(pattern): an order of Patterns
#   and hash() of an object are compile-time errors in Pystachy; test_pattern_compare_bytes: bytes.
# - test_ignore_case_range's [N-\uffff], [n-\uffff], [N-\U00010000] and [n-\U00010000] with
#   IGNORECASE|ASCII: the port's compiler case-folds such a range code point by code point, with
#   two lists for each (lib/re/__init__.py, _optimize_charset), 250,000 allocations, which take
#   over a minute in make verify's run with a collection at each (gc-stress). tools/re_fuzz.py
#   checks them against CPython's re (the code they compile to and their matches).
# - PatternReprTests.test_long_pattern's 1,000 longs: 100 here (its repr is cut at 200 characters
#   either way), as compiling 5,000 characters' items takes 80,000 allocations, 17 seconds in make
#   verify's gc-stress; tools/re_fuzz.py checks the 1,000.
# - DebugTests (re.DEBUG's dump) and ImplementationTest (CPython's internals: re._compiler,
#   _sre, immutable C types, deprecated modules): the port has no DEBUG output or C types.
# - test_pickling, test_copying, test_weakref, test_keep_buffer, test_empty_array, test_dealloc,
#   test_memory_leaks: pickle, copy, weakref, buffers, arrays and debug builds.
import re


def at(s: str, i: int) -> str:
    # a position in s: the index, or in non-ASCII text the text before it (Pystachy's index counts
    # UTF-8 bytes there, a documented deviation, but slices out the same text)
    if i < 0 or s.isascii():
        return str(i)
    return repr(s[:i])


def show(m) -> str:
    # a match: its span and its groups
    if m is None:
        return "None"
    s = m.string
    out = "(%s, %s) %r" % (at(s, m.start()), at(s, m.end()), m.group(0))
    if m.re.groups > 0:
        out += " %r" % [m.group(i) for i in range(1, m.re.groups + 1)]
    return out


def run(how: str, pattern: str, string: str, flags: int) -> re.Match | None:
    p = re.compile(pattern, flags)
    if how == "match":
        return p.match(string)
    if how == "fullmatch":
        return p.fullmatch(string)
    return p.search(string)


M, S, F = "match", "search", "fullmatch"
I, IA = re.I, re.I | re.A
upper_char = '\u1ea0'  # Latin Capital Letter A with Dot Below
lower_char = '\u1ea1'  # Latin Small Letter A with Dot Below
CASES = [
    # test_flags
    (M, '^pattern$', 'pattern', re.I), (M, '^pattern$', 'pattern', re.M), (M, '^pattern$', 'pattern', re.X),
    (M, '^pattern$', 'pattern', re.S), (M, '^pattern$', 'pattern', re.A), (M, '^pattern$', 'pattern', re.U),
    # test_ignore_case
    (M, "abc", "ABC", I), (M, r"(a\s[^a])", "a b", I), (M, r"(a\s[^a]*)", "a bb", I), (M, r"(a\s[abc])", "a b", I),
    (M, r"(a\s[abc]*)", "a bb", I), (M, r"((a)\s\2)", "a a", I), (M, r"((a)\s\2*)", "a aa", I),
    (M, r"((a)\s(abc|a))", "a a", I), (M, r"((a)\s(abc|a)*)", "a aa", I),
    (M, r'K', '\u212a', I), (M, r'k', '\u212a', I), (M, r'\u212a', 'K', I), (M, r'\u212a', 'k', I),
    (M, r'S', '\u017f', I), (M, r's', '\u017f', I), (M, r'\u017f', 'S', I), (M, r'\u017f', 's', I),
    (M, r'\u0412', '\u0432', I), (M, r'\u0412', '\u1c80', I), (M, r'\u0432', '\u0412', I), (M, r'\u0432', '\u1c80', I),
    (M, r'\u1c80', '\u0412', I), (M, r'\u1c80', '\u0432', I), (M, r'\ufb05', '\ufb06', I), (M, r'\ufb06', '\ufb05', I),
    # test_ignore_case_set
    (M, r'[19A]', 'A', I), (M, r'[19a]', 'a', I), (M, r'[19a]', 'A', I), (M, r'[19A]', 'a', I),
    (M, r'[19\xc7]', '\xc7', I), (M, r'[19\xc7]', '\xe7', I), (M, r'[19\xe7]', '\xc7', I), (M, r'[19\xe7]', '\xe7', I),
    (M, r'[19\u0400]', '\u0400', I), (M, r'[19\u0400]', '\u0450', I), (M, r'[19\u0450]', '\u0400', I),
    (M, r'[19\u0450]', '\u0450', I), (M, r'[19\U00010400]', '\U00010400', I), (M, r'[19\U00010400]', '\U00010428', I),
    (M, r'[19\U00010428]', '\U00010400', I), (M, r'[19\U00010428]', '\U00010428', I),
    (M, r'[19A]', 'A', IA), (M, r'[19a]', 'a', IA), (M, r'[19a]', 'A', IA), (M, r'[19A]', 'a', IA),
    (M, r'[19\xc7]', '\xc7', IA), (M, r'[19\xc7]', '\xe7', IA), (M, r'[19\xe7]', '\xc7', IA), (M, r'[19\xe7]', '\xe7', IA),
    (M, r'[19\u0400]', '\u0400', IA), (M, r'[19\u0400]', '\u0450', IA), (M, r'[19\u0450]', '\u0400', IA),
    (M, r'[19\u0450]', '\u0450', IA), (M, r'[19\U00010400]', '\U00010400', IA),
    (M, r'[19\U00010400]', '\U00010428', IA), (M, r'[19\U00010428]', '\U00010400', IA),
    (M, r'[19\U00010428]', '\U00010428', IA),
    (M, r'[19K]', '\u212a', I), (M, r'[19k]', '\u212a', I), (M, r'[19\u212a]', 'K', I), (M, r'[19\u212a]', 'k', I),
    (M, r'[19S]', '\u017f', I), (M, r'[19s]', '\u017f', I), (M, r'[19\u017f]', 'S', I), (M, r'[19\u017f]', 's', I),
    (M, r'[19\u0412]', '\u0432', I), (M, r'[19\u0412]', '\u1c80', I), (M, r'[19\u0432]', '\u0412', I),
    (M, r'[19\u0432]', '\u1c80', I), (M, r'[19\u1c80]', '\u0412', I), (M, r'[19\u1c80]', '\u0432', I),
    (M, r'[19\ufb05]', '\ufb06', I), (M, r'[19\ufb06]', '\ufb05', I),
    # test_ignore_case_range
    (M, r'[9-a]', '_', I), (M, r'[9-A]', '_', I), (M, r'[\xc0-\xde]', '\xd7', I), (M, r'[\xc0-\xde]', '\xe7', I),
    (M, r'[\xc0-\xde]', '\xf7', I), (M, r'[\xe0-\xfe]', '\xf7', I), (M, r'[\xe0-\xfe]', '\xc7', I),
    (M, r'[\xe0-\xfe]', '\xd7', I), (M, r'[\u0430-\u045f]', '\u0450', I), (M, r'[\u0430-\u045f]', '\u0400', I),
    (M, r'[\u0400-\u042f]', '\u0450', I), (M, r'[\u0400-\u042f]', '\u0400', I),
    (M, r'[\U00010428-\U0001044f]', '\U00010428', I), (M, r'[\U00010428-\U0001044f]', '\U00010400', I),
    (M, r'[\U00010400-\U00010427]', '\U00010428', I), (M, r'[\U00010400-\U00010427]', '\U00010400', I),
    (M, r'[\xc0-\xde]', '\xd7', IA), (M, r'[\xc0-\xde]', '\xe7', IA), (M, r'[\xe0-\xfe]', '\xf7', IA),
    (M, r'[\xe0-\xfe]', '\xc7', IA), (M, r'[\u0430-\u045f]', '\u0450', IA), (M, r'[\u0430-\u045f]', '\u0400', IA),
    (M, r'[\u0400-\u042f]', '\u0450', IA), (M, r'[\u0400-\u042f]', '\u0400', IA),
    (M, r'[\U00010428-\U0001044f]', '\U00010428', IA), (M, r'[\U00010428-\U0001044f]', '\U00010400', IA),
    (M, r'[\U00010400-\U00010427]', '\U00010428', IA), (M, r'[\U00010400-\U00010427]', '\U00010400', IA),
    (M, r'[N-\x7f]', 'A', IA), (M, r'[n-\x7f]', 'Z', IA),
    (M, r'[J-M]', '\u212a', I), (M, r'[j-m]', '\u212a', I), (M, r'[\u2129-\u212b]', 'K', I),
    (M, r'[\u2129-\u212b]', 'k', I), (M, r'[R-T]', '\u017f', I), (M, r'[r-t]', '\u017f', I),
    (M, r'[\u017e-\u0180]', 'S', I), (M, r'[\u017e-\u0180]', 's', I), (M, r'[\u0411-\u0413]', '\u0432', I),
    (M, r'[\u0411-\u0413]', '\u1c80', I), (M, r'[\u0431-\u0433]', '\u0412', I), (M, r'[\u0431-\u0433]', '\u1c80', I),
    (M, r'[\u1c80-\u1c82]', '\u0412', I), (M, r'[\u1c80-\u1c82]', '\u0432', I), (M, r'[\ufb04-\ufb05]', '\ufb06', I),
    (M, r'[\ufb06-\ufb07]', '\ufb05', I),
    # test_bug_20998
    (F, '[a-c]+', 'ABC', I),
    # test_inline_flags
    (M, '.' + upper_char, '\n' + lower_char, re.I | re.S), (M, '.' + lower_char, '\n' + upper_char, re.I | re.S),
    (M, '(?i).' + upper_char, '\n' + lower_char, re.S), (M, '(?i).' + lower_char, '\n' + upper_char, re.S),
    (M, '(?is).' + upper_char, '\n' + lower_char, 0), (M, '(?is).' + lower_char, '\n' + upper_char, 0),
    (M, '(?s)(?i).' + upper_char, '\n' + lower_char, 0), (M, '(?s)(?i).' + lower_char, '\n' + upper_char, 0),
    (M, '(?ix) ' + upper_char, lower_char, 0), (M, '(?ix) ' + lower_char, upper_char, 0),
    (M, ' (?i) ' + upper_char, lower_char, re.X), (M, '(?x) (?i) ' + upper_char, lower_char, 0),
    (M, ' (?x) (?i) ' + upper_char, lower_char, re.X),
    # test_ascii_and_unicode_flag
    (M, '\xc0', '\xe0', re.I), (M, r'\w', '\xe0', 0), (M, '\xc0', '\xe0', re.U | re.I), (M, r'\w', '\xe0', re.U),
    (M, '\xc0', '\xe0', re.A | re.I), (M, '(?a)\xc0', '\xe0', re.I), (M, r'\w', '\xe0', re.A), (M, r'(?a)\w', '\xe0', 0),
    # test_scoped_flags
    (M, r'(?i:a)b', 'Ab', 0), (M, r'(?i:a)b', 'aB', 0), (M, r'(?-i:a)b', 'Ab', I), (M, r'(?-i:a)b', 'aB', I),
    (M, r'(?i:(?-i:a)b)', 'Ab', 0), (M, r'(?i:(?-i:a)b)', 'aB', 0), (M, r'\w(?a:\W)\w', '\xe0\xe0\xe0', 0),
    (M, r'(?a:\W(?u:\w)\W)', '\xe0\xe0\xe0', 0), (M, r'\W(?u:\w)\W', '\xe0\xe0\xe0', re.A),
    # test_ignore_spaces
    (F, ' a', 'a', re.X), (F, '\ta', 'a', re.X), (F, '\na', 'a', re.X), (F, '\ra', 'a', re.X), (F, '\va', 'a', re.X),
    (F, '\fa', 'a', re.X), (F, '(?x) a', 'a', 0), (F, ' (?x) a', 'a', re.X), (F, '(?x) (?x) a', 'a', 0),
    (F, ' a(?x: b) c', ' ab c', 0), (F, ' a(?-x: b) c', 'a bc', re.X), (F, '(?x) a(?-x: b) c', 'a bc', 0),
    (F, '(?x) a| b', 'a', 0), (F, '(?x) a| b', 'b', 0),
    # test_comments
    (F, '#x\na', 'a', re.X), (F, '(?x)#x\na', 'a', 0), (F, '#x\n(?x)#y\na', 'a', re.X), (F, '(?x)#x\n(?x)#y\na', 'a', 0),
    (F, '#x\na(?x:#y\nb)#z\nc', '#x\nab#z\nc', 0), (F, '#x\na(?-x:#y\nb)#z\nc', 'a#y\nbc', re.X),
    (F, '(?x)#x\na(?-x:#y\nb)#z\nc', 'a#y\nbc', 0), (F, '(?x)#x\na|#y\nb', 'a', 0), (F, '(?x)#x\na|#y\nb', 'b', 0),
    # test_special_escapes
    (S, r"\b(b.)\b", "abcd abc bcd bx", 0), (S, r"\B(b.)\B", "abc bcd bc abxd", 0),
    (S, r"\b(b.)\b", "abcd abc bcd bx", re.A), (S, r"\B(b.)\B", "abc bcd bc abxd", re.A),
    (S, r"^abc$", "\nabc\n", re.M), (S, r"^\Aabc\Z$", "abc", re.M), (S, r"^\Aabc\Z$", "\nabc\n", re.M),
    (S, r"\d\D\w\W\s\S", "1aa! a", 0), (S, r"\d\D\w\W\s\S", "1aa! a", re.A),
    # test_other_escapes
    (M, r"\(", '(', 0), (M, r"\(", ')', 0), (M, r"\\", '\\', 0), (M, r"[\]]", ']', 0), (M, r"[\]]", '[', 0),
    (M, r"[a\-c]", '-', 0), (M, r"[a\-c]", 'b', 0), (M, r"[\^a]+", 'a^', 0), (M, r"[\^a]+", 'b', 0),
    # test_word_boundaries
    (S, r"\b(abc)\b", "abc", 0), (S, r"\b(abc)\b", "abc", re.A), (S, r"\b(ьюя)\b", "ьюя", 0),
    (S, r"\b(ьюя)\b", "ьюя", re.A), (M, r".\b", "a=", 0), (M, r".\b", "a=", re.A), (M, r".\b", "я=", 0),
    (M, r".\b", "я=", re.A), (M, r".\b", "=a", 0), (M, r".\b", "=a", re.A), (M, r".\b", "=я", 0), (M, r".\b", "=я", re.A),
    (M, r".\b", "ab", 0), (M, r".\b", "ab", re.A), (M, r".\b", "юя", 0), (M, r".\b", "юя", re.A), (M, r".\b", "=-", 0),
    (M, r".\b", "=-", re.A), (M, r".\B", "a=", 0), (M, r".\B", "a=", re.A), (M, r".\B", "я=", 0), (M, r".\B", "я=", re.A),
    (M, r".\B", "=a", 0), (M, r".\B", "=a", re.A), (M, r".\B", "=я", 0), (M, r".\B", "=я", re.A), (M, r".\B", "ab", 0),
    (M, r".\B", "ab", re.A), (M, r".\B", "юя", 0), (M, r".\B", "юя", re.A), (M, r".\B", "=-", 0), (M, r".\B", "=-", re.A),
    (M, r"\b", "abc", 0), (M, r"\b", "abc", re.A), (M, r"\b", "ьюя", 0), (M, r"\b", "ьюя", re.A), (F, r".+\b", "abc", 0),
    (F, r".+\b", "abc", re.A), (F, r".+\b", "ьюя", 0), (S, r"\b", "ьюя", re.A), (S, r"\B", "abc", 0),
    (S, r"\B", "abc", re.A), (S, r"\B", "ьюя", 0), (S, r"\B", "ьюя", re.A), (M, r"\B", "abc", 0), (M, r"\B", "abc", re.A),
    (M, r"\B", "ьюя", 0), (M, r"\B", "ьюя", re.A), (F, r".+\B", "abc", 0), (F, r".+\B", "abc", re.A),
    (F, r".+\B", "ьюя", 0), (F, r".+\B", "ьюя", re.A), (S, r"\b", "", 0), (S, r"\b", "", re.A), (S, r"\B", "", 0),
    (S, r"\B", "", re.A),
    # test_anyall
    (M, "a.b", "a\nb", re.S), (M, "a.*b", "a\n\nb", re.S),
    # test_bug_6561: \d is the Unicode decimal digits (category Nd), not Nl or No
    (M, r'^\d$', '\u0037', 0), (M, r'^\d$', '\u0e58', 0), (M, r'^\d$', '\uff10', 0), (M, r'^\d$', '\u2165', 0),
    (M, r'^\d$', '\u3039', 0), (M, r'^\d$', '\u2082', 0), (M, r'^\d$', '\u32b4', 0),
    # test_search_dot_unicode
    (S, "123.*-", '123abc-', 0), (S, "123.*-", '123\xe9-', 0), (S, "123.*-", '123\u20ac-', 0),
    (S, "123.*-", '123\U0010ffff-', 0), (S, "123.*-", '123\xe9\u20ac\U0010ffff-', 0),
    # test_category, test_not_literal, test_search_coverage
    (M, r"(\s)", " ", 0), (S, r"\s([^a])", " b", 0), (S, r"\s([^a]*)", " bb", 0), (S, r"\s(b)", " b", 0),
    (S, r"a\s", "a ", 0),
    # test_bigcharset
    (M, "([\u2222\u2223])", "\u2222", 0), (M, '[%s]' % ''.join([chr(i) for i in range(256, 2**16, 255)]), "\uff01", 0),
    # test_bug_612074
    (M, "[" + re.escape("\u2039") + "]", "\u2039", 0),
    # test_sre_character_class_literals
    (M, r"[\U0001d49c-\U0001d4b5]", "\U0001d49e", 0),
]
for how, pattern, string, flags in CASES:
    print(how, repr(pattern), repr(string), int(flags), show(run(how, pattern, string, flags)))

# test_word_boundaries: the number of boundaries in a string
for pattern, string in [(r"\b", "a"), (r"\B", "a"), (r"\b", " "), (r"\b", "   "), (r"\B", " ")]:
    print("findall", repr(pattern), repr(string), len(re.findall(pattern, string)), len(re.findall(pattern, string, re.A)))

# test_sre_character_literals, test_sre_character_class_literals: each escape of a character, as
# a literal and in a class (chr(i) is "%c" % i)
for i in [0, 8, 16, 32, 64, 127, 128, 255, 256, 0xFFFF, 0x10000, 0x10FFFF]:
    c = "%c" % i
    pats: list[tuple[str, str]] = []
    if i < 256:
        pats += [(r"\%03o" % i, c), (r"\%03o0" % i, c + "0"), (r"\%03o8" % i, c + "8"), (r"\x%02x" % i, c),
                 (r"\x%02x0" % i, c + "0"), (r"\x%02xz" % i, c + "z"), (r"[\%o]" % i, c), (r"[\%o8]" % i, c),
                 (r"[\%03o]" % i, c), (r"[\%03o0]" % i, c), (r"[\%03o8]" % i, c), (r"[\x%02x]" % i, c),
                 (r"[\x%02x0]" % i, c), (r"[\x%02xz]" % i, c)]
    if i < 0x10000:
        pats += [(r"\u%04x" % i, c), (r"\u%04x0" % i, c + "0"), (r"\u%04xz" % i, c + "z"), (r"[\u%04x]" % i, c),
                 (r"[\u%04x0]" % i, c), (r"[\u%04xz]" % i, c)]
    pats += [(r"\U%08x" % i, c), (r"\U%08x0" % i, c + "0"), (r"\U%08xz" % i, c + "z"), (r"[\U%08x]" % i, c),
             (r"[\U%08x0]" % i, c + "0"), (r"[\U%08xz]" % i, c + "z")]
    print(i, " ".join([show(re.match(p, s)) for p, s in pats]))
for p, s in [(r"\0", "\000"), (r"\08", "\0008"), (r"\01", "\001"), (r"\018", "\0018")]:
    print(repr(p), show(re.match(p, s)))

# test_re_escape: each character below 256 escaped matches itself, alone, in a class and verbose
n = 0
whole = ""
for i in range(256):
    c = "%c" % i
    whole += c
    for p in [re.escape(c), '[' + re.escape(c) + ']', '(?x)' + re.escape(c)]:
        m = re.fullmatch(p, c)
        assert m is not None and m.group() == c and m.span() == (0, len(c))
        n += 1
m = re.fullmatch(re.escape(whole), whole)
assert m is not None and m.group() == whole and m.span() == (0, len(whole))
print(n, [re.escape(c)[:1] for c in '-.]{}'], repr(re.escape(whole[:128])))
LITERAL_CHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ' + '0123456789' + '!"%\',/:;<=>@_`'
print(re.escape(LITERAL_CHARS) == LITERAL_CHARS)

# test_constants
print(re.I == re.IGNORECASE, re.L == re.LOCALE, re.M == re.MULTILINE, re.S == re.DOTALL, re.X == re.VERBOSE,
      int(re.A), int(re.I), int(re.L), int(re.M), int(re.S), int(re.U), int(re.X), int(re.NOFLAG))

# test_getattr
pg = re.compile("(?i)(a)(b)")
print(pg.pattern, int(pg.flags), int(re.I | re.U), pg.groups, dict(pg.groupindex))
pg = re.compile("(?i)(?P<first>a)(?P<other>b)")
print(dict(pg.groupindex), sorted(pg.groupindex), pg.groupindex['other'])
m = re.match("(a)", "a")
assert m is not None
print(m.pos, m.endpos, m.string, m.re is re.compile("(a)"), m.lastindex)

# test_compile
pattern0 = re.compile('random pattern')
same_pattern = re.compile(pattern0)
print(isinstance(pattern0, re.Pattern), isinstance(same_pattern, re.Pattern), same_pattern is pattern0)

# test_pattern_compare
pattern1 = re.compile('abc', re.IGNORECASE)
print(pattern1 == pattern1, pattern1 != pattern1)
re.purge()
pattern2 = re.compile('abc', re.IGNORECASE)
print(pattern2 == pattern1)
re.purge()
pattern3 = re.compile('XYZ', re.IGNORECASE)
print(pattern3 != pattern1)
re.purge()
pattern4 = re.compile('abc')
print(pattern4 != pattern1)

# test_match_repr
m = re.search(r'(.+)(.*?)\1', '[abracadabra]')
print(repr(m))
ms = [x for x in re.finditer("(aa)|(bb)", "aa bb")]
print(len(ms), repr(ms[0]), repr(ms[1]))

# PatternReprTests
print(repr(re.compile('random pattern')))
print(repr(re.compile('random pattern', re.IGNORECASE)))
print(repr(re.compile('random pattern', re.I | re.S | re.X)))
print(repr(re.compile('random pattern', re.U)))
print(repr(re.compile('random pattern', re.I | re.S | re.U)))
print(repr(re.compile('(?i)pattern')))
print(repr(re.compile('random pattern', 0x123000)))
print(repr(re.compile('random pattern', 0x123000 | re.I)))
print(repr(re.compile('random "double quoted" pattern')))
print(repr(re.compile("random 'single quoted' pattern")))
print(repr(re.compile('''both 'single' and "double" quotes''')))
pattern = 'Very %spattern' % ('long ' * 100)
r = repr(re.compile(pattern))
print(len(r) < 300, r[:30], r)
r = repr(re.compile(pattern, re.I))
print(len(r) < 300, r[:30], r[-16:])
