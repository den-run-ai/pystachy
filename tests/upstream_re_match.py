# Adapted from CPython 3.13.16 Lib/test/test_re.py, commit cbc944f4bc59639a444dd971c737788ba2283a91:
# the matches that ReTests checks for backtracking and the groups it restores
# (test_search_star_plus, test_branching, test_re_match, test_group, test_match_getitem,
# test_re_fullmatch, test_re_groupref_exists, test_bug_3629,
# test_re_groupref_exists_validation_bug, test_re_groupref, test_symbolic_groups,
# test_repeat_minmax, test_lookahead, test_lookbehind, test_bug_113254, test_bug_527371,
# test_bug_418626, test_stack_overflow, test_unlimited_zero_width_repeat, test_bug_448951,
# test_bug_725106, test_bug_725149, test_bug_2537, test_bug_34294, test_MARK_PUSH_macro_bug,
# test_MIN_UNTIL_mark_bug, test_REPEAT_ONE_mark_bug, test_MIN_REPEAT_ONE_mark_bug,
# test_ASSERT_NOT_mark_bug, test_possessive_quantifiers, test_fullmatch_possessive_quantifiers,
# test_atomic_grouping, test_fullmatch_atomic_grouping, test_bug_gh91616, test_bug_gh100061,
# test_bug_gh101955, test_fail, test_character_set_any, test_character_set_none,
# test_keyword_parameters, test_repeat_minmax_overflow, test_look_behind_overflow,
# test_regression_gh94675, test_search_anchor_at_beginning, test_big_codesize and
# test_large_search).
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
#
# Each case runs through lib/re, Pystachy's port of re, compiled; this file's .out was recorded
# with CPython's own re. The unittest scaffolding becomes a table of (function, pattern, string,
# flags) cases, and each prints its match: the span, each group's value and span, lastindex and
# lastgroup, a superset of what upstream asserts. m.groups() is printed as the list of
# m.group(i), and findall() of 2 groups or more as the groups of each finditer() match.
#
# EXCLUDED (not in the tables):
# - bytes patterns and strings, str subclasses (S, B, test_bug_764548) and memoryview/bytearray
#   subjects: the port has str patterns and strs only.
# - test_re_match's groups("") default is covered in tuple_runtime_regex.py; these tables
#   retain their per-group output. groupdict() with a default is in upstream_re_sub.py.
# - test_group's Index objects (__index__) and 1<<1000, test_match_getitem's format_map(), item
#   assignment and len(): unsupported (64-bit ints, no __index__ groups, no format_map).
# - test_getattr's m.regs, and groupindex as a mappingproxy (a dict in the port): documented
#   deviations; the other attributes are in upstream_re_flags.py.
# - test_regression_gh94675's multiprocessing timeout: the substitution runs here directly.
# - upstream's sizes where a case is about size: make verify runs this program with a collection
#   at every allocation (gc-stress), where each of the port's allocations scans the live heap,
#   the decoded string and the compiled code included. The same code paths run here on smaller
#   inputs: test_bug_418626 on 1/20 of its strings (1,001 to 3,001 characters, not 20,001 to
#   60,001), test_stack_overflow on 2,500 repeats (not 50,000), test_search_anchor_at_beginning on
#   10**4 characters (not 10**7, and without its CPU-time bound), test_big_codesize on 300
#   alternatives (not 10,000), test_look_behind_overflow's searches with a lookbehind 8**3 = 512
#   characters wide on 600 (not 2**21 on 2,500,000; its 2**22-wide patterns compile here as
#   upstream's do), and test_large_search on 10**3 characters (not 2**31, a bigmem test).
#   tools/re_fuzz.py runs the first five at upstream's sizes (but 10**6 characters for
#   test_search_anchor_at_beginning), the port on CPython against CPython's re.
import re


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
    out = "(%s, %s) %r" % (at(s, m.start()), at(s, m.end()), m.group(0))
    if m.re.groups > 0:
        values: list[str | None] = []
        spans: list[str] = []
        for i in range(1, m.re.groups + 1):
            values.append(m.group(i))
            spans.append("(%s, %s)" % (at(s, m.start(i)), at(s, m.end(i))))
        out += " %r %s last=%s/%s" % (values, " ".join(spans), m.lastindex, m.lastgroup)
    return out


def run(how: str, pattern: str, string: str, flags: int) -> re.Match | None:
    p = re.compile(pattern, flags)
    if how == "match":
        return p.match(string)
    if how == "fullmatch":
        return p.fullmatch(string)
    return p.search(string)


M, S, F = "match", "search", "fullmatch"
CASES = [
    # test_search_star_plus
    (S, 'x*', 'axx', 0), (S, 'x+', 'axx', 0), (S, 'x', 'aaa', 0), (M, 'a*', 'xxx', 0), (M, 'x*', 'xxxa', 0),
    (M, 'a+', 'xxx', 0),
    # test_branching
    (M, '(ab|ba)', 'ab', 0), (M, '(ab|ba)', 'ba', 0), (M, '(abc|bac|ca|cb)', 'abc', 0),
    (M, '(abc|bac|ca|cb)', 'bac', 0), (M, '(abc|bac|ca|cb)', 'ca', 0), (M, '(abc|bac|ca|cb)', 'cb', 0),
    (M, '((a)|(b)|(c))', 'a', 0), (M, '((a)|(b)|(c))', 'b', 0), (M, '((a)|(b)|(c))', 'c', 0),
    # test_re_match
    (M, 'a', 'a', 0), (M, '(a)', 'a', 0), (M, '\xe0', '\xe0', 0), (M, '(\xe0)', '\xe0', 0),
    (M, 'а', 'а', 0), (M, '(а)', 'а', 0), (M, '\U0001d49c', '\U0001d49c', 0),
    (M, '(\U0001d49c)', '\U0001d49c', 0),
    (M, '((a)|(b))(c)?', 'a', 0), (M, '((a)|(b))(c)?', 'b', 0), (M, '((a)|(b))(c)?', 'ac', 0),
    (M, '((a)|(b))(c)?', 'bc', 0),
    (M, '(?:(?P<a1>a)|(?P<b2>b))(?P<c3>c)?', 'a', 0), (M, '(?:(?P<a1>a)|(?P<b2>b))(?P<c3>c)?', 'b', 0),
    (M, '(?:(?P<a1>a)|(?P<b2>b))(?P<c3>c)?', 'ac', 0),
    # test_re_fullmatch
    (F, r"a", "a", 0), (F, r"a|ab", "ab", 0), (F, r"\xe0|\xe0\xdf", "\xe0\xdf", 0),
    (F, r"а|аб", "аб", 0), (F, "\U0001d49c|\U0001d49c\U0001d49e", "\U0001d49c\U0001d49e", 0),
    (F, r".*?$", "abc", 0), (F, r".*?", "abc", 0), (F, r"a.*?b", "ab", 0), (F, r"a.*?b", "abb", 0),
    (F, r"a.*?b", "axxb", 0), (F, r"a+", "ab", 0), (F, r"abc$", "abc\n", 0), (F, r"abc\Z", "abc\n", 0),
    (F, r"(?m)abc$", "abc\n", 0), (F, r"ab(?=c)cd", "abcd", 0), (F, r"ab(?<=b)cd", "abcd", 0),
    (F, r"(?=a|ab)ab", "ab", 0),
    # test_re_groupref_exists
    (M, r'^(\()?([^()]+)(?(1)\))$', '(a)', 0), (M, r'^(\()?([^()]+)(?(1)\))$', 'a', 0),
    (M, r'^(\()?([^()]+)(?(1)\))$', 'a)', 0), (M, r'^(\()?([^()]+)(?(1)\))$', '(a', 0),
    (M, '^(?:(a)|c)((?(1)b|d))$', 'ab', 0), (M, r'^(?:(a)|c)((?(1)b|d))$', 'cd', 0),
    (M, r'^(?:(a)|c)((?(1)|d))$', 'cd', 0), (M, r'^(?:(a)|c)((?(1)|d))$', 'a', 0),
    (M, '(?P<g1>a)(?P<g2>b)?((?(g2)c|d))', 'abc', 0), (M, '(?P<g1>a)(?P<g2>b)?((?(g2)c|d))', 'ad', 0),
    (M, '(?P<g1>a)(?P<g2>b)?((?(g2)c|d))', 'abd', 0), (M, '(?P<g1>a)(?P<g2>b)?((?(g2)c|d))', 'ac', 0),
    # test_bug_3629
    (M, "(?P<quote>)(?(quote))", "", 0),
    # test_re_groupref
    (M, r'^(\|)?([^()]+)\1$', '|a|', 0), (M, r'^(\|)?([^()]+)\1?$', 'a', 0), (M, r'^(\|)?([^()]+)\1$', 'a|', 0),
    (M, r'^(\|)?([^()]+)\1$', '|a', 0), (M, r'^(?:(a)|c)(\1)$', 'aa', 0), (M, r'^(?:(a)|c)(\1)?$', 'c', 0),
    # test_symbolic_groups
    (M, r'(?P<a>x)(?P=a)(?(a)y)', 'xxy', 0), (M, r'(?P<a1>x)(?P=a1)(?(a1)y)', 'xxy', 0),
    (M, r'(?P<a1>x)\1(?(1)y)', 'xxy', 0), (M, '(?P<µ>x)(?P=µ)(?(µ)y)', 'xxy', 0),
    (M, '(?P<𝔘𝔫𝔦𝔠𝔬𝔡𝔢>x)(?P=𝔘𝔫𝔦𝔠𝔬𝔡𝔢)(?(𝔘𝔫𝔦𝔠𝔬𝔡𝔢)y)', 'xxy', 0),
    # test_repeat_minmax
    (M, r"^(\w){1}$", "abc", 0), (M, r"^(\w){1}?$", "abc", 0), (M, r"^(\w){1,2}$", "abc", 0),
    (M, r"^(\w){1,2}?$", "abc", 0), (M, r"^(\w){3}$", "abc", 0), (M, r"^(\w){1,3}$", "abc", 0),
    (M, r"^(\w){1,4}$", "abc", 0), (M, r"^(\w){3,4}?$", "abc", 0), (M, r"^(\w){3}?$", "abc", 0),
    (M, r"^(\w){1,3}?$", "abc", 0), (M, r"^(\w){1,4}?$", "abc", 0), (M, r"^x{1}$", "xxx", 0),
    (M, r"^x{1}?$", "xxx", 0), (M, r"^x{1,2}$", "xxx", 0), (M, r"^x{1,2}?$", "xxx", 0), (M, r"^x{3}$", "xxx", 0),
    (M, r"^x{1,3}$", "xxx", 0), (M, r"^x{3,3}$", "xxx", 0), (M, r"^x{1,4}$", "xxx", 0), (M, r"^x{3,4}?$", "xxx", 0),
    (M, r"^x{3}?$", "xxx", 0), (M, r"^x{1,3}?$", "xxx", 0), (M, r"^x{1,4}?$", "xxx", 0), (M, r"^x{}$", "xxx", 0),
    (M, r"^x{}$", "x{}", 0),
    # test_lookahead
    (M, r"(a(?=\s[^a]))", "a b", 0), (M, r"(a(?=\s[^a]*))", "a b", 0), (M, r"(a(?=\s[abc]))", "a b", 0),
    (M, r"(a(?=\s[abc]*))", "a bc", 0), (M, r"(a)(?=\s\1)", "a a", 0), (M, r"(a)(?=\s\1*)", "a aa", 0),
    (M, r"(a)(?=\s(abc|a))", "a a", 0), (M, r"(a(?!\s[^a]))", "a a", 0), (M, r"(a(?!\s[abc]))", "a d", 0),
    (M, r"(a)(?!\s\1)", "a b", 0), (M, r"(a)(?!\s(abc|a))", "a b", 0), (M, r'(a)b(?=\1)a', 'aba', 0),
    (M, r'(a)b(?=\1)c', 'abac', 0), (M, r'(?:(a)|(x))b(?=(?(2)x|c))c', 'abc', 0),
    (M, r'(?:(a)|(x))b(?=(?(2)c|x))c', 'abc', 0), (M, r'(?:(a)|(x))b(?=(?(1)b|x))c', 'abc', 0),
    (M, r'(?:(a)|(x))b(?=(?(1)c|x))c', 'abc', 0), (M, r'(a)b(?=(?(2)x|c))(c)', 'abc', 0),
    (M, r'(a)b(?=(?(2)b|x))(c)', 'abc', 0), (M, r'(a)b(?=(?(1)c|x))(c)', 'abc', 0),
    # test_lookbehind
    (M, r'ab(?<=b)c', 'abc', 0), (M, r'ab(?<=c)c', 'abc', 0), (M, r'ab(?<!b)c', 'abc', 0), (M, r'ab(?<!c)c', 'abc', 0),
    (M, r'(a)a(?<=\1)c', 'aac', 0), (M, r'(a)b(?<=\1)a', 'abaa', 0), (M, r'(a)a(?<!\1)c', 'aac', 0),
    (M, r'(a)b(?<!\1)a', 'abaa', 0), (M, r'(?:(a)|(x))b(?<=(?(2)x|c))c', 'abc', 0),
    (M, r'(?:(a)|(x))b(?<=(?(2)b|x))c', 'abc', 0), (M, r'(?:(a)|(x))b(?<=(?(2)x|b))c', 'abc', 0),
    (M, r'(?:(a)|(x))b(?<=(?(1)c|x))c', 'abc', 0), (M, r'(?:(a)|(x))b(?<=(?(1)b|x))c', 'abc', 0),
    (M, r'(a)b(?<=(?(1)c|x))(c)', 'abc', 0), (M, r'(a)b(?<=(?(1)b|x))(c)', 'abc', 0),
    # test_bug_113254
    (M, r'(a)|(b)', 'b', 0),
    # test_bug_527371
    (M, r'(a)?a', 'a', 0), (M, r'(a)(b)?b', 'ab', 0), (M, r'(?P<a>a)(?P<b>b)?b', 'ab', 0),
    (M, r"(?P<a>a(b))", "ab", 0), (M, r"((a))", "a", 0),
    # test_unlimited_zero_width_repeat
    (M, r'(?:a?)*y', 'z', 0), (M, r'(?:a?)+y', 'z', 0), (M, r'(?:a?){2,}y', 'z', 0), (M, r'(?:a?)*?y', 'z', 0),
    (M, r'(?:a?)+?y', 'z', 0), (M, r'(?:a?){2,}?y', 'z', 0),
    # test_bug_448951
    (M, r'((.):)?z', 'z', 0), (M, r'((.):)?z', 'a:z', 0), (M, r'((.?):)?z', 'z', 0), (M, r'((.?):)?z', 'a:z', 0),
    (M, r'((.*):)?z', 'z', 0), (M, r'((.*):)?z', 'a:z', 0),
    # test_bug_725106: capturing groups in alternatives in repeats
    (M, '^((a)|b)*', 'abc', 0), (M, '^(([ab])|c)*', 'abc', 0), (M, '^((d)|[ab])*', 'abc', 0),
    (M, '^((a)c|[ab])*', 'abc', 0), (M, '^((a)|b)*?c', 'abc', 0), (M, '^(([ab])|c)*?d', 'abcd', 0),
    (M, '^((d)|[ab])*?c', 'abc', 0), (M, '^((a)c|[ab])*?c', 'abc', 0),
    # test_bug_725149: mark_stack_base restoring before restoring marks
    (M, '(a)(?:(?=(b)*)c)*', 'abb', 0), (M, '(a)((?!(b)*))*', 'abb', 0),
    # test_bug_34294
    (S, r"\b(?=(\t)|(x))x", "a\tx", 0),
    # test_MARK_PUSH_macro_bug
    (M, r'(ab|a)*?b', 'ab', 0), (M, r'(ab|a)+?b', 'ab', 0), (M, r'(ab|a){0,2}?b', 'ab', 0), (M, r'(.b|a)*?b', 'ab', 0),
    # test_MIN_UNTIL_mark_bug
    (M, r'(?:(?:a|bc)*?(xx)??z)*', 'axxzbcz', 0), (M, r'((x|yz)+?(t)??c)*', 'xtcxyzxc', 0),
    # test_REPEAT_ONE_mark_bug
    (M, r'(?:[^b]*a(?=(b)|(a))ab)*', 'aabaab', 0), (M, r'(?:[^b]*(?=(b)|(a))ab)*', 'abab', 0),
    (M, r'(ab?)*?b', 'ab', 0),
    # test_MIN_REPEAT_ONE_mark_bug
    (M, r'(?:.*?(?=(a)|(b))b)*', 'abab', 0), (M, r'(?:a*?(xx)??z)*', 'axxzaz', 0),
    # test_ASSERT_NOT_mark_bug
    (M, r'(?!(..)c)', 'ab', 0), (M, r'((?!(ab)c)(.))*', 'abab', 0),
    # test_possessive_quantifiers
    (M, 'e*+e', 'eeee', 0), (M, 'e++a', 'eeea', 0), (M, 'e?+a', 'ea', 0), (M, 'e{2,4}+a', 'eeea', 0),
    (M, '(.)++.', 'ee', 0), (M, '(ae)*+a', 'aea', 0), (M, '([ae][ae])?+a', 'aea', 0), (M, '(e?){2,4}+a', 'eeea', 0),
    (M, '()*+a', 'a', 0), (S, 'x*+', 'axx', 0), (S, 'x++', 'axx', 0), (M, 'a*+', 'xxx', 0), (M, 'x*+', 'xxxa', 0),
    (M, 'a++', 'xxx', 0), (M, r"^(\w){1}+$", "abc", 0), (M, r"^(\w){1,2}+$", "abc", 0), (M, r"^(\w){3}+$", "abc", 0),
    (M, r"^(\w){1,3}+$", "abc", 0), (M, r"^(\w){1,4}+$", "abc", 0), (M, "^x{1}+$", "xxx", 0),
    (M, "^x{1,2}+$", "xxx", 0), (M, "^x{3}+$", "xxx", 0), (M, "^x{1,3}+$", "xxx", 0), (M, "^x{1,4}+$", "xxx", 0),
    (M, "^x{}+$", "xxx", 0), (M, "^x{}+$", "x{}", 0),
    # test_fullmatch_possessive_quantifiers
    (F, r'a++', 'a', 0), (F, r'a*+', 'a', 0), (F, r'a?+', 'a', 0), (F, r'a{1,3}+', 'a', 0), (F, r'a++', 'ab', 0),
    (F, r'a*+', 'ab', 0), (F, r'a?+', 'ab', 0), (F, r'a{1,3}+', 'ab', 0), (F, r'a++b', 'ab', 0), (F, r'a*+b', 'ab', 0),
    (F, r'a?+b', 'ab', 0), (F, r'a{1,3}+b', 'ab', 0), (F, r'(?:ab)++', 'ab', 0), (F, r'(?:ab)*+', 'ab', 0),
    (F, r'(?:ab)?+', 'ab', 0), (F, r'(?:ab){1,3}+', 'ab', 0), (F, r'(?:ab)++', 'abc', 0), (F, r'(?:ab)*+', 'abc', 0),
    (F, r'(?:ab)?+', 'abc', 0), (F, r'(?:ab){1,3}+', 'abc', 0), (F, r'(?:ab)++c', 'abc', 0),
    (F, r'(?:ab)*+c', 'abc', 0), (F, r'(?:ab)?+c', 'abc', 0), (F, r'(?:ab){1,3}+c', 'abc', 0),
    # test_atomic_grouping
    (M, r'a(?>bc|b)c', 'abc', 0), (M, r'a(?>bc|b)c', 'abcc', 0), (M, r'(?>.*).', 'abc', 0), (M, r'(?>x)++', 'xxx', 0),
    (M, r'(?>x++)', 'xxx', 0), (M, r'(?>x)++x', 'xxx', 0), (M, r'(?>x++)x', 'xxx', 0),
    # test_fullmatch_atomic_grouping
    (F, r'(?>a+)', 'a', 0), (F, r'(?>a*)', 'a', 0), (F, r'(?>a?)', 'a', 0), (F, r'(?>a{1,3})', 'a', 0),
    (F, r'(?>a+)', 'ab', 0), (F, r'(?>a*)', 'ab', 0), (F, r'(?>a?)', 'ab', 0), (F, r'(?>a{1,3})', 'ab', 0),
    (F, r'(?>a+)b', 'ab', 0), (F, r'(?>a*)b', 'ab', 0), (F, r'(?>a?)b', 'ab', 0), (F, r'(?>a{1,3})b', 'ab', 0),
    (F, r'(?>(?:ab)+)', 'ab', 0), (F, r'(?>(?:ab)*)', 'ab', 0), (F, r'(?>(?:ab)?)', 'ab', 0),
    (F, r'(?>(?:ab){1,3})', 'ab', 0), (F, r'(?>(?:ab)+)', 'abc', 0), (F, r'(?>(?:ab)*)', 'abc', 0),
    (F, r'(?>(?:ab)?)', 'abc', 0), (F, r'(?>(?:ab){1,3})', 'abc', 0), (F, r'(?>(?:ab)+)c', 'abc', 0),
    (F, r'(?>(?:ab)*)c', 'abc', 0), (F, r'(?>(?:ab)?)c', 'abc', 0), (F, r'(?>(?:ab){1,3})c', 'abc', 0),
    # test_bug_gh91616
    (F, r'(?s:(?>.*?\.).*)\Z', "a.txt", 0), (F, r'(?s:(?=(?P<g0>.*?\.))(?P=g0).*)\Z', "a.txt", 0),
    # test_bug_gh100061 and gh-106052
    (M, '(?>(?:.(?!D))+)', 'ABCDE', 0), (M, '(?:.(?!D))++', 'ABCDE', 0), (M, '(?>(?:.(?!D))*)', 'ABCDE', 0),
    (M, '(?:.(?!D))*+', 'ABCDE', 0), (M, '(?>(?:.(?!D))?)', 'CDE', 0), (M, '(?:.(?!D))?+', 'CDE', 0),
    (M, '(?>(?:.(?!D)){1,3})', 'ABCDE', 0), (M, '(?:.(?!D)){1,3}+', 'ABCDE', 0), (M, "(?>(?:ab?c)+)", "aca", 0),
    (M, "(?:ab?c)++", "aca", 0), (M, "(?>(?:ab?c)*)", "aca", 0), (M, "(?:ab?c)*+", "aca", 0),
    (M, "(?>(?:ab?c)?)", "a", 0), (M, "(?:ab?c)?+", "a", 0), (M, "(?>(?:ab?c){1,3})", "aca", 0),
    (M, "(?:ab?c){1,3}+", "aca", 0),
    # test_bug_gh101955: possessive quantifier with nested alternative with capture groups
    (M, '((x)|y|z)*+', 'xyz', 0), (M, '((x)|y|z){3}+', 'xyz', 0), (M, '((x)|y|z){3,}+', 'xyz', 0),
    # test_fail
    (S, r'12(?!)|3', '123', 0),
    # test_character_set_any, test_character_set_none
    (F, r'(?:[\s\S])+', '1x\n', 0), (F, r'(?:[\d\D])+', '1x\n', 0), (F, r'(?:[\w\W])+', '1x\n', 0),
    (F, r'(?:[\S\s])+', '1x\n', 0), (F, r'(?:\s|\S)+', '1x\n', 0), (S, r'[^\s\S]', '1x\n', 0),
    (S, r'[^\d\D]', '1x\n', 0), (S, r'[^\w\W]', '1x\n', 0), (S, r'[^\S\s]', '1x\n', 0), (S, r'(?s:.)[^\s\S]', '1x\n', 0),
    (S, r'(?s:.)[^\d\D]', '1x\n', 0), (S, r'(?s:.)[^\w\W]', '1x\n', 0), (S, r'(?s:.)[^\S\s]', '1x\n', 0),
]
for how, pattern, string, flags in CASES:
    print(how, repr(pattern), repr(string), show(run(how, pattern, string, flags)))

# test_bug_2537: empty submatches
for outer_op in ('{0,}', '*', '+', '{1,187}'):
    for inner_op in ('{0,}', '*', '?'):
        r = re.compile("^((x|y)%s)%s" % (inner_op, outer_op))
        print("bug_2537", repr(r.pattern), show(r.match("xyyzy")))

# test_re_match, test_group, test_match_getitem: groups by number, name and several at once
m = re.match('(a)', 'a')
assert m is not None
print(m.group(0), m.group(1), m.group(1, 1))
pat = re.compile('(?:(?P<a1>a)|(?P<b2>b))(?P<c3>c)?')
for s in ['a', 'b', 'ac']:
    m = pat.match(s)
    assert m is not None
    print(repr(s), m.group(1, 2, 3), m.group('a1', 'b2', 'c3'), m.group(1, 'b2', 3), m['a1'], m['b2'], m['c3'],
          m[0], m[1], m[2], m[3])
m = re.match('(a)(b)', 'ab')
assert m is not None
print(m.group(), m.group(0), m.group(1), m.group(2, 1))

# test_bug_113254: a group that took no part has span (-1, -1)
m = re.match(r'(a)|(b)', 'b')
assert m is not None
print(m.start(1), m.end(1), m.span(1))

# test_re_fullmatch and test_keyword_parameters: pos and endpos, also as keywords
print(show(re.compile(r"bc").fullmatch("abcd", pos=1, endpos=3)), show(re.compile(r".*?$").fullmatch("abcd", pos=1, endpos=3)),
      show(re.compile(r".*?").fullmatch("abcd", pos=1, endpos=3)))
pat = re.compile(r'(ab)')
print(show(pat.match(string='abracadabra', pos=7, endpos=10)), show(pat.fullmatch(string='abracadabra', pos=7, endpos=9)),
      show(pat.search(string='abracadabra', pos=3, endpos=10)), pat.findall(string='abracadabra', pos=3, endpos=10),
      pat.split(string='abracadabra', maxsplit=1))

# test_symbolic_groups, test_re_groupref_exists: more than 100 groups
pat200 = '|'.join(['x(?P<a%d>%x)y' % (i, i) for i in range(1, 200 + 1)])
for p in ['(?:%s)(?(200)z|t)' % pat200, '(?:%s)(?(200)z)' % pat200]:
    m = re.match(p, 'xc8yz')
    assert m is not None
    print(m.span(), m.group(200), m.group(199), m.lastindex, m.lastgroup)

# test_re_groupref_exists_validation_bug: a conditional whose branch is an optional \xNN
n = 0
for i in range(256):
    n += re.compile(r'()(?(1)\x%02x?)' % i).groups
print(n)

# test_bug_418626: '*?' on long strings (SRE_OP_MIN_REPEAT_ONE, and the non-recursive scheme), on
# 1/20 of upstream's strings
m = re.match('.*?c', 500 * 'ab' + 'cd')
print(m.end(0) if m is not None else None)
m = re.match('.*?cd', 250 * 'ab' + 'c' + 250 * 'ab' + 'cde')
print(m.end(0) if m is not None else None)
m = re.match('.*?cd', 1000 * 'abc' + 'de')
print(m.end(0) if m is not None else None)
m = re.search('(a|b)*?c', 500 * 'ab' + 'cd')
print(m.end(0) if m is not None else None)

# test_stack_overflow: repeated groups 2,500 times over (upstream: 50,000)
m = re.match('(x)*', 2500 * 'x')
print(m.group(1) if m is not None else None, m.span() if m is not None else None)
m = re.match('(x)*y', 2500 * 'x' + 'y')
print(m.group(1) if m is not None else None, m.span() if m is not None else None)
m = re.match('(x)*?y', 2500 * 'x' + 'y')
print(m.group(1) if m is not None else None, m.span() if m is not None else None)

# test_repeat_minmax_overflow: repeat counts past 65535
string = "x" * 100000
for p in [r".{65535}", r".{,65535}", r".{65535,}?", r".{65536}", r".{,65536}", r".{65536,}?"]:
    m = re.match(p, string)
    print(repr(p), m.span() if m is not None else None)

# test_look_behind_overflow: a lookbehind of nested repeats 8**3 characters wide (upstream: 2**21),
# and ones 2**22 wide, which compile
string = "x" * 600
m = re.search(r"(?<=((.{%d}){%d}){%d})" % (8, 8, 8), string)
print(m.span() if m is not None else None)
m = re.search(r"(?<!((.{%d}){%d}){%d})" % (8, 8, 8), string)
print(m.span() if m is not None else None)
for a, b, c in [(2**22, 1, 1), (1, 2**22, 1), (1, 1, 2**22)]:
    print(re.compile(r"(?<=((.{%d}){%d}){%d})" % (a, b, c)).groups, re.compile(r"(?<!((.{%d}){%d}){%d})" % (a, b, c)).groups)

# test_search_anchor_at_beginning (on 10**4 characters)
s = 'x' * 10**4
for p in [r'\Ay', r'^y']:
    print(repr(p), re.search(p, s), re.split(p, s) == [s], re.findall(p, s), [mm.span() for mm in re.finditer(p, s)],
          re.sub(p, '', s) == s)

# test_big_codesize (300 alternatives)
r = re.compile('|'.join(['%d' % x for x in range(300)]))
print(show(r.match('100')), show(r.match('299')), len(r.pattern))

# test_large_search (on 10**3 characters, not 2**31)
s = 'a' * 10**3
m = re.search('$', s)
print(m.start() if m is not None else None, m.end() if m is not None else None)

# test_regression_gh94675: this substitution once ran (practically) forever
js_pattern = re.compile(r'(?<=[({}])(((//[^\n]*)?[\n])([\000-\040])*)*'
                        r'((/[^/\[\n]*(([^\n]|(\[\n]*(]*)*\]))'
                        r'[^/\[]*)*/))((((//[^\n]*)?[\n])'
                        r'([\000-\040]|(/\*[^*]*\*+'
                        r'([^/*]\*+)*/))*)+(?=[^\000-\040);\]}]))')
input_js = '''a(function() {
            ///////////////////////////////////////////////////////////////////
        });'''
print(repr(js_pattern.sub("", input_js)))
