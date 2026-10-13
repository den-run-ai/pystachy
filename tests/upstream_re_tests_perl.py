# Adapted from CPython 3.13.16 Lib/test/re_tests.py (its tests table from "All tests from Perl" on;
# tests/upstream_re_tests.py runs the cases before) and Lib/test/test_re.py
# (ExternalTests.test_re_tests, which runs them), commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
#
# Every case runs through lib/re, Pystachy's port of re, compiled; this file's .out was recorded
# with CPython's own re. The table is re_tests.py's, with its comments; the edits are mechanical:
# a 3-tuple (pattern, string, outcome) has '' and '' for its expression and expected value (a
# Pystachy list holds one tuple type), chr(255) is written '\xff' (chr() of i < 256 is a byte in
# Pystachy, docs/language.md), the \N{LATIN CAPITAL LETTER A WITH DIAERESIS} escape is written
# '\xc4' (Pystachy's literals have no \N{...}), and "[SUCCEED, FAIL, SYNTAX_ERROR] = range(3)"
# binds the three names one by one. test_re_tests's eval() of a case's expression in its dict of
# groups becomes value() below (an expression is "+" of found, gN, a group's name and str
# literals). Each case prints the match (its span, each group's value and span, lastindex and
# lastgroup) and the expression's value, which it asserts as upstream does, then the subtests'
# searches: within the match's span plus one ("range"), with IGNORECASE ("I") and with UNICODE
# ("U"), "=" where one gives the case's own match. The cases are numbered by their place in
# upstream's list.
#
# EXCLUDED: test_re_tests's "bytes pattern match" and "locale-sensitive match" subtests (bytes
# patterns, and LOCALE, which only they take): the port has str patterns only. The range-limited
# search of the 3 matches in a string that is not ASCII ('\377', and 'Ä' twice): there the end of
# the match plus one is a byte index inside a character in Pystachy, a documented deviation
# (tests/deviations/lib_re.py); their positions print as the text before them (see at()).
import re

# The 3 possible outcomes for each pattern
SUCCEED, FAIL, SYNTAX_ERROR = 0, 1, 2

tests = [
    # All tests from Perl

    ('ab{0,}bc', 'abbbbc', SUCCEED, 'found', 'abbbbc'),
    ('ab{1,}bc', 'abq', FAIL, '', ''),
    ('ab{1,}bc', 'abbbbc', SUCCEED, 'found', 'abbbbc'),
    ('ab{1,3}bc', 'abbbbc', SUCCEED, 'found', 'abbbbc'),
    ('ab{3,4}bc', 'abbbbc', SUCCEED, 'found', 'abbbbc'),
    ('ab{4,5}bc', 'abbbbc', FAIL, '', ''),
    ('ab{0,1}bc', 'abc', SUCCEED, 'found', 'abc'),
    ('ab{0,1}c', 'abc', SUCCEED, 'found', 'abc'),
    ('^', 'abc', SUCCEED, 'found', ''),
    ('$', 'abc', SUCCEED, 'found', ''),
    ('a[b-]', 'a-', SUCCEED, 'found', 'a-'),
    ('a[b-a]', '-', SYNTAX_ERROR, '', ''),
    ('*a', '-', SYNTAX_ERROR, '', ''),
    ('(*)b', '-', SYNTAX_ERROR, '', ''),
    ('a{1,}b{1,}c', 'aabbabc', SUCCEED, 'found', 'abc'),
    ('a**', '-', SYNTAX_ERROR, '', ''),
    ('a.+?c', 'abcabc', SUCCEED, 'found', 'abc'),
    ('(a+|b){0,}', 'ab', SUCCEED, 'found+"-"+g1', 'ab-b'),
    ('(a+|b){1,}', 'ab', SUCCEED, 'found+"-"+g1', 'ab-b'),
    ('(a+|b){0,1}', 'ab', SUCCEED, 'found+"-"+g1', 'a-a'),
    ('([abc])*d', 'abbbcd', SUCCEED, 'found+"-"+g1', 'abbbcd-c'),
    ('([abc])*bcd', 'abcd', SUCCEED, 'found+"-"+g1', 'abcd-a'),
    ('^(ab|cd)e', 'abcde', FAIL, '', ''),
    ('((((((((((a))))))))))', 'a', SUCCEED, 'g10', 'a'),
    ('((((((((((a))))))))))\\10', 'aa', SUCCEED, 'found', 'aa'),
# Python does not have the same rules for \\41 so this is a syntax error
#    ('((((((((((a))))))))))\\41', 'aa', FAIL, '', ''),
#    ('((((((((((a))))))))))\\41', 'a!', SUCCEED, 'found', 'a!'),
    ('((((((((((a))))))))))\\41', '', SYNTAX_ERROR, '', ''),
    ('(?i)((((((((((a))))))))))\\41', '', SYNTAX_ERROR, '', ''),
    ('(?i)abc', 'ABC', SUCCEED, 'found', 'ABC'),
    ('(?i)abc', 'XBC', FAIL, '', ''),
    ('(?i)abc', 'AXC', FAIL, '', ''),
    ('(?i)abc', 'ABX', FAIL, '', ''),
    ('(?i)abc', 'XABCY', SUCCEED, 'found', 'ABC'),
    ('(?i)abc', 'ABABC', SUCCEED, 'found', 'ABC'),
    ('(?i)ab*c', 'ABC', SUCCEED, 'found', 'ABC'),
    ('(?i)ab*bc', 'ABC', SUCCEED, 'found', 'ABC'),
    ('(?i)ab*bc', 'ABBC', SUCCEED, 'found', 'ABBC'),
    ('(?i)ab*?bc', 'ABBBBC', SUCCEED, 'found', 'ABBBBC'),
    ('(?i)ab{0,}?bc', 'ABBBBC', SUCCEED, 'found', 'ABBBBC'),
    ('(?i)ab+?bc', 'ABBC', SUCCEED, 'found', 'ABBC'),
    ('(?i)ab+bc', 'ABC', FAIL, '', ''),
    ('(?i)ab+bc', 'ABQ', FAIL, '', ''),
    ('(?i)ab{1,}bc', 'ABQ', FAIL, '', ''),
    ('(?i)ab+bc', 'ABBBBC', SUCCEED, 'found', 'ABBBBC'),
    ('(?i)ab{1,}?bc', 'ABBBBC', SUCCEED, 'found', 'ABBBBC'),
    ('(?i)ab{1,3}?bc', 'ABBBBC', SUCCEED, 'found', 'ABBBBC'),
    ('(?i)ab{3,4}?bc', 'ABBBBC', SUCCEED, 'found', 'ABBBBC'),
    ('(?i)ab{4,5}?bc', 'ABBBBC', FAIL, '', ''),
    ('(?i)ab??bc', 'ABBC', SUCCEED, 'found', 'ABBC'),
    ('(?i)ab??bc', 'ABC', SUCCEED, 'found', 'ABC'),
    ('(?i)ab{0,1}?bc', 'ABC', SUCCEED, 'found', 'ABC'),
    ('(?i)ab??bc', 'ABBBBC', FAIL, '', ''),
    ('(?i)ab??c', 'ABC', SUCCEED, 'found', 'ABC'),
    ('(?i)ab{0,1}?c', 'ABC', SUCCEED, 'found', 'ABC'),
    ('(?i)^abc$', 'ABC', SUCCEED, 'found', 'ABC'),
    ('(?i)^abc$', 'ABCC', FAIL, '', ''),
    ('(?i)^abc', 'ABCC', SUCCEED, 'found', 'ABC'),
    ('(?i)^abc$', 'AABC', FAIL, '', ''),
    ('(?i)abc$', 'AABC', SUCCEED, 'found', 'ABC'),
    ('(?i)^', 'ABC', SUCCEED, 'found', ''),
    ('(?i)$', 'ABC', SUCCEED, 'found', ''),
    ('(?i)a.c', 'ABC', SUCCEED, 'found', 'ABC'),
    ('(?i)a.c', 'AXC', SUCCEED, 'found', 'AXC'),
    ('(?i)a.*?c', 'AXYZC', SUCCEED, 'found', 'AXYZC'),
    ('(?i)a.*c', 'AXYZD', FAIL, '', ''),
    ('(?i)a[bc]d', 'ABC', FAIL, '', ''),
    ('(?i)a[bc]d', 'ABD', SUCCEED, 'found', 'ABD'),
    ('(?i)a[b-d]e', 'ABD', FAIL, '', ''),
    ('(?i)a[b-d]e', 'ACE', SUCCEED, 'found', 'ACE'),
    ('(?i)a[b-d]', 'AAC', SUCCEED, 'found', 'AC'),
    ('(?i)a[-b]', 'A-', SUCCEED, 'found', 'A-'),
    ('(?i)a[b-]', 'A-', SUCCEED, 'found', 'A-'),
    ('(?i)a[b-a]', '-', SYNTAX_ERROR, '', ''),
    ('(?i)a[]b', '-', SYNTAX_ERROR, '', ''),
    ('(?i)a[', '-', SYNTAX_ERROR, '', ''),
    ('(?i)a]', 'A]', SUCCEED, 'found', 'A]'),
    ('(?i)a[]]b', 'A]B', SUCCEED, 'found', 'A]B'),
    ('(?i)a[^bc]d', 'AED', SUCCEED, 'found', 'AED'),
    ('(?i)a[^bc]d', 'ABD', FAIL, '', ''),
    ('(?i)a[^-b]c', 'ADC', SUCCEED, 'found', 'ADC'),
    ('(?i)a[^-b]c', 'A-C', FAIL, '', ''),
    ('(?i)a[^]b]c', 'A]C', FAIL, '', ''),
    ('(?i)a[^]b]c', 'ADC', SUCCEED, 'found', 'ADC'),
    ('(?i)ab|cd', 'ABC', SUCCEED, 'found', 'AB'),
    ('(?i)ab|cd', 'ABCD', SUCCEED, 'found', 'AB'),
    ('(?i)()ef', 'DEF', SUCCEED, 'found+"-"+g1', 'EF-'),
    ('(?i)*a', '-', SYNTAX_ERROR, '', ''),
    ('(?i)(*)b', '-', SYNTAX_ERROR, '', ''),
    ('(?i)$b', 'B', FAIL, '', ''),
    ('(?i)a\\', '-', SYNTAX_ERROR, '', ''),
    ('(?i)a\\(b', 'A(B', SUCCEED, 'found+"-"+g1', 'A(B-Error'),
    ('(?i)a\\(*b', 'AB', SUCCEED, 'found', 'AB'),
    ('(?i)a\\(*b', 'A((B', SUCCEED, 'found', 'A((B'),
    ('(?i)a\\\\b', 'A\\B', SUCCEED, 'found', 'A\\B'),
    ('(?i)abc)', '-', SYNTAX_ERROR, '', ''),
    ('(?i)(abc', '-', SYNTAX_ERROR, '', ''),
    ('(?i)((a))', 'ABC', SUCCEED, 'found+"-"+g1+"-"+g2', 'A-A-A'),
    ('(?i)(a)b(c)', 'ABC', SUCCEED, 'found+"-"+g1+"-"+g2', 'ABC-A-C'),
    ('(?i)a+b+c', 'AABBABC', SUCCEED, 'found', 'ABC'),
    ('(?i)a{1,}b{1,}c', 'AABBABC', SUCCEED, 'found', 'ABC'),
    ('(?i)a**', '-', SYNTAX_ERROR, '', ''),
    ('(?i)a.+?c', 'ABCABC', SUCCEED, 'found', 'ABC'),
    ('(?i)a.*?c', 'ABCABC', SUCCEED, 'found', 'ABC'),
    ('(?i)a.{0,5}?c', 'ABCABC', SUCCEED, 'found', 'ABC'),
    ('(?i)(a+|b)*', 'AB', SUCCEED, 'found+"-"+g1', 'AB-B'),
    ('(?i)(a+|b){0,}', 'AB', SUCCEED, 'found+"-"+g1', 'AB-B'),
    ('(?i)(a+|b)+', 'AB', SUCCEED, 'found+"-"+g1', 'AB-B'),
    ('(?i)(a+|b){1,}', 'AB', SUCCEED, 'found+"-"+g1', 'AB-B'),
    ('(?i)(a+|b)?', 'AB', SUCCEED, 'found+"-"+g1', 'A-A'),
    ('(?i)(a+|b){0,1}', 'AB', SUCCEED, 'found+"-"+g1', 'A-A'),
    ('(?i)(a+|b){0,1}?', 'AB', SUCCEED, 'found+"-"+g1', '-None'),
    ('(?i))(', '-', SYNTAX_ERROR, '', ''),
    ('(?i)[^ab]*', 'CDE', SUCCEED, 'found', 'CDE'),
    ('(?i)abc', '', FAIL, '', ''),
    ('(?i)a*', '', SUCCEED, 'found', ''),
    ('(?i)([abc])*d', 'ABBBCD', SUCCEED, 'found+"-"+g1', 'ABBBCD-C'),
    ('(?i)([abc])*bcd', 'ABCD', SUCCEED, 'found+"-"+g1', 'ABCD-A'),
    ('(?i)a|b|c|d|e', 'E', SUCCEED, 'found', 'E'),
    ('(?i)(a|b|c|d|e)f', 'EF', SUCCEED, 'found+"-"+g1', 'EF-E'),
    ('(?i)abcd*efg', 'ABCDEFG', SUCCEED, 'found', 'ABCDEFG'),
    ('(?i)ab*', 'XABYABBBZ', SUCCEED, 'found', 'AB'),
    ('(?i)ab*', 'XAYABBBZ', SUCCEED, 'found', 'A'),
    ('(?i)(ab|cd)e', 'ABCDE', SUCCEED, 'found+"-"+g1', 'CDE-CD'),
    ('(?i)[abhgefdc]ij', 'HIJ', SUCCEED, 'found', 'HIJ'),
    ('(?i)^(ab|cd)e', 'ABCDE', FAIL, '', ''),
    ('(?i)(abc|)ef', 'ABCDEF', SUCCEED, 'found+"-"+g1', 'EF-'),
    ('(?i)(a|b)c*d', 'ABCD', SUCCEED, 'found+"-"+g1', 'BCD-B'),
    ('(?i)(ab|ab*)bc', 'ABC', SUCCEED, 'found+"-"+g1', 'ABC-A'),
    ('(?i)a([bc]*)c*', 'ABC', SUCCEED, 'found+"-"+g1', 'ABC-BC'),
    ('(?i)a([bc]*)(c*d)', 'ABCD', SUCCEED, 'found+"-"+g1+"-"+g2', 'ABCD-BC-D'),
    ('(?i)a([bc]+)(c*d)', 'ABCD', SUCCEED, 'found+"-"+g1+"-"+g2', 'ABCD-BC-D'),
    ('(?i)a([bc]*)(c+d)', 'ABCD', SUCCEED, 'found+"-"+g1+"-"+g2', 'ABCD-B-CD'),
    ('(?i)a[bcd]*dcdcde', 'ADCDCDE', SUCCEED, 'found', 'ADCDCDE'),
    ('(?i)a[bcd]+dcdcde', 'ADCDCDE', FAIL, '', ''),
    ('(?i)(ab|a)b*c', 'ABC', SUCCEED, 'found+"-"+g1', 'ABC-AB'),
    ('(?i)((a)(b)c)(d)', 'ABCD', SUCCEED, 'g1+"-"+g2+"-"+g3+"-"+g4', 'ABC-A-B-D'),
    ('(?i)[a-zA-Z_][a-zA-Z0-9_]*', 'ALPHA', SUCCEED, 'found', 'ALPHA'),
    ('(?i)^a(bc+|b[eh])g|.h$', 'ABH', SUCCEED, 'found+"-"+g1', 'BH-None'),
    ('(?i)(bc+d$|ef*g.|h?i(j|k))', 'EFFGZ', SUCCEED, 'found+"-"+g1+"-"+g2', 'EFFGZ-EFFGZ-None'),
    ('(?i)(bc+d$|ef*g.|h?i(j|k))', 'IJ', SUCCEED, 'found+"-"+g1+"-"+g2', 'IJ-IJ-J'),
    ('(?i)(bc+d$|ef*g.|h?i(j|k))', 'EFFG', FAIL, '', ''),
    ('(?i)(bc+d$|ef*g.|h?i(j|k))', 'BCDD', FAIL, '', ''),
    ('(?i)(bc+d$|ef*g.|h?i(j|k))', 'REFFGZ', SUCCEED, 'found+"-"+g1+"-"+g2', 'EFFGZ-EFFGZ-None'),
    ('(?i)((((((((((a))))))))))', 'A', SUCCEED, 'g10', 'A'),
    ('(?i)((((((((((a))))))))))\\10', 'AA', SUCCEED, 'found', 'AA'),
    #('(?i)((((((((((a))))))))))\\41', 'AA', FAIL, '', ''),
    #('(?i)((((((((((a))))))))))\\41', 'A!', SUCCEED, 'found', 'A!'),
    ('(?i)(((((((((a)))))))))', 'A', SUCCEED, 'found', 'A'),
    ('(?i)(?:(?:(?:(?:(?:(?:(?:(?:(?:(a))))))))))', 'A', SUCCEED, 'g1', 'A'),
    ('(?i)(?:(?:(?:(?:(?:(?:(?:(?:(?:(a|b|c))))))))))', 'C', SUCCEED, 'g1', 'C'),
    ('(?i)multiple words of text', 'UH-UH', FAIL, '', ''),
    ('(?i)multiple words', 'MULTIPLE WORDS, YEAH', SUCCEED, 'found', 'MULTIPLE WORDS'),
    ('(?i)(.*)c(.*)', 'ABCDE', SUCCEED, 'found+"-"+g1+"-"+g2', 'ABCDE-AB-DE'),
    ('(?i)\\((.*), (.*)\\)', '(A, B)', SUCCEED, 'g2+"-"+g1', 'B-A'),
    ('(?i)[k]', 'AB', FAIL, '', ''),
#    ('(?i)abcd', 'ABCD', SUCCEED, 'found+"-"+\\found+"-"+\\\\found', 'ABCD-$&-\\ABCD'),
#    ('(?i)a(bc)d', 'ABCD', SUCCEED, 'g1+"-"+\\g1+"-"+\\\\g1', 'BC-$1-\\BC'),
    ('(?i)a[-]?c', 'AC', SUCCEED, 'found', 'AC'),
    ('(?i)(abc)\\1', 'ABCABC', SUCCEED, 'g1', 'ABC'),
    ('(?i)([a-c]*)\\1', 'ABCABC', SUCCEED, 'g1', 'ABC'),
    ('a(?!b).', 'abad', SUCCEED, 'found', 'ad'),
    ('a(?=d).', 'abad', SUCCEED, 'found', 'ad'),
    ('a(?=c|d).', 'abad', SUCCEED, 'found', 'ad'),
    ('a(?:b|c|d)(.)', 'ace', SUCCEED, 'g1', 'e'),
    ('a(?:b|c|d)*(.)', 'ace', SUCCEED, 'g1', 'e'),
    ('a(?:b|c|d)+?(.)', 'ace', SUCCEED, 'g1', 'e'),
    ('a(?:b|(c|e){1,2}?|d)+?(.)', 'ace', SUCCEED, 'g1 + g2', 'ce'),

    # lookbehind: split by : but not if it is escaped by -.
    ('(?<!-):(.*?)(?<!-):', 'a:bc-:de:f', SUCCEED, 'g1', 'bc-:de' ),
    # escaping with \ as we know it
    ('(?<!\\\\):(.*?)(?<!\\\\):', 'a:bc\\:de:f', SUCCEED, 'g1', 'bc\\:de' ),
    # terminating with ' and escaping with ? as in edifact
    ("(?<!\\?)'(.*?)(?<!\\?)'", "a'bc?'de'f", SUCCEED, 'g1', "bc?'de" ),

    # Comments using the (?#...) syntax

    ('w(?# comment', 'w', SYNTAX_ERROR, '', ''),
    ('w(?# comment 1)xy(?# comment 2)z', 'wxyz', SUCCEED, 'found', 'wxyz'),

    # Check odd placement of embedded pattern modifiers

    # not an error under PCRE/PRE:
    ('(?i)w', 'W', SUCCEED, 'found', 'W'),
    # ('w(?i)', 'W', SYNTAX_ERROR, '', ''),

    # Comments using the x embedded pattern modifier

    ("""(?x)w# comment 1
        x y
        # comment 2
        z""", 'wxyz', SUCCEED, 'found', 'wxyz'),

    # using the m embedded pattern modifier

    ('^abc', """jkl
abc
xyz""", FAIL, '', ''),
    ('(?m)^abc', """jkl
abc
xyz""", SUCCEED, 'found', 'abc'),

    ('(?m)abc$', """jkl
xyzabc
123""", SUCCEED, 'found', 'abc'),



    # test \w, etc. both inside and outside character classes

    ('\\w+', '--ab_cd0123--', SUCCEED, 'found', 'ab_cd0123'),
    ('[\\w]+', '--ab_cd0123--', SUCCEED, 'found', 'ab_cd0123'),
    ('\\D+', '1234abc5678', SUCCEED, 'found', 'abc'),
    ('[\\D]+', '1234abc5678', SUCCEED, 'found', 'abc'),
    ('[\\da-fA-F]+', '123abc', SUCCEED, 'found', '123abc'),
    # not an error under PCRE/PRE:
    # ('[\\d-x]', '-', SYNTAX_ERROR, '', ''),
    (r'([\s]*)([\S]*)([\s]*)', ' testing!1972', SUCCEED, 'g3+g2+g1', 'testing!1972 '),
    (r'(\s*)(\S*)(\s*)', ' testing!1972', SUCCEED, 'g3+g2+g1', 'testing!1972 '),

    (r'\xff', '\377', SUCCEED, 'found', '\xff'),
    # new \x semantics
    (r'\x00ff', '\377', FAIL, '', ''),
    # (r'\x00ff', '\377', SUCCEED, 'found', '\xff'),
    (r'\t\n\v\r\f\a', '\t\n\v\r\f\a', SUCCEED, 'found', '\t\n\v\r\f\a'),
    ('\t\n\v\r\f\a', '\t\n\v\r\f\a', SUCCEED, 'found', '\t\n\v\r\f\a'),
    (r'\t\n\v\r\f\a', '\t\n\v\r\f\a', SUCCEED, 'found', chr(9)+chr(10)+chr(11)+chr(13)+chr(12)+chr(7)),
    (r'[\t][\n][\v][\r][\f][\b]', '\t\n\v\r\f\b', SUCCEED, 'found', '\t\n\v\r\f\b'),

    #
    # post-1.5.2 additions

    # xmllib problem
    (r'(([a-z]+):)?([a-z]+)$', 'smil', SUCCEED, 'g1+"-"+g2+"-"+g3', 'None-None-smil'),
    # bug 110866: reference to undefined group
    (r'((.)\1+)', '', SYNTAX_ERROR, '', ''),
    # bug 111869: search (PRE/PCRE fails on this one, SRE doesn't)
    (r'.*d', 'abc\nabd', SUCCEED, 'found', 'abd'),
    # bug 112468: various expected syntax errors
    (r'(', '', SYNTAX_ERROR, '', ''),
    (r'[\41]', '!', SUCCEED, 'found', '!'),
    # bug 114033: nothing to repeat
    (r'(x?)?', 'x', SUCCEED, 'found', 'x'),
    # bug 115040: rescan if flags are modified inside pattern
    (r'(?x) foo ', 'foo', SUCCEED, 'found', 'foo'),
    # bug 115618: negative lookahead
    (r'(?<!abc)(d.f)', 'abcdefdof', SUCCEED, 'found', 'dof'),
    # bug 116251: character class bug
    (r'[\w-]+', 'laser_beam', SUCCEED, 'found', 'laser_beam'),
    # bug 123769+127259: non-greedy backtracking bug
    (r'.*?\S *:', 'xx:', SUCCEED, 'found', 'xx:'),
    (r'a[ ]*?\ (\d+).*', 'a   10', SUCCEED, 'found', 'a   10'),
    (r'a[ ]*?\ (\d+).*', 'a    10', SUCCEED, 'found', 'a    10'),
    # bug 127259: \Z shouldn't depend on multiline mode
    (r'(?ms).*?x\s*\Z(.*)','xx\nx\n', SUCCEED, 'g1', ''),
    # bug 128899: uppercase literals under the ignorecase flag
    (r'(?i)M+', 'MMM', SUCCEED, 'found', 'MMM'),
    (r'(?i)m+', 'MMM', SUCCEED, 'found', 'MMM'),
    (r'(?i)[M]+', 'MMM', SUCCEED, 'found', 'MMM'),
    (r'(?i)[m]+', 'MMM', SUCCEED, 'found', 'MMM'),
    # bug 130748: ^* should be an error (nothing to repeat)
    (r'^*', '', SYNTAX_ERROR, '', ''),
    # bug 133283: minimizing repeat problem
    (r'"(?:\\"|[^"])*?"', r'"\""', SUCCEED, 'found', r'"\""'),
    # bug 477728: minimizing repeat problem
    (r'^.*?$', 'one\ntwo\nthree\n', FAIL, '', ''),
    # bug 483789: minimizing repeat problem
    (r'a[^>]*?b', 'a>b', FAIL, '', ''),
    # bug 490573: minimizing repeat problem
    (r'^a*?$', 'foo', FAIL, '', ''),
    # bug 470582: nested groups problem
    (r'^((a)c)?(ab)$', 'ab', SUCCEED, 'g1+"-"+g2+"-"+g3', 'None-None-ab'),
    # another minimizing repeat problem (capturing groups in assertions)
    ('^([ab]*?)(?=(b)?)c', 'abc', SUCCEED, 'g1+"-"+g2', 'ab-None'),
    ('^([ab]*?)(?!(b))c', 'abc', SUCCEED, 'g1+"-"+g2', 'ab-None'),
    ('^([ab]*?)(?<!(a))c', 'abc', SUCCEED, 'g1+"-"+g2', 'ab-None'),
]

u = '\xc4'  # (upstream: '\N{LATIN CAPITAL LETTER A WITH DIAERESIS}')
tests.extend([
    # bug 410271: \b broken under locales
    (r'\b.\b', 'a', SUCCEED, 'found', 'a'),
    (r'(?u)\b.\b', u, SUCCEED, 'found', u),
    (r'(?u)\w', u, SUCCEED, 'found', u),
])


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
n = 189  # (the cases before these are tests/upstream_re_tests.py's)
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
