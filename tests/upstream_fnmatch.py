# Adapted from CPython 3.13.16 Lib/test/test_fnmatch.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91. PSF License v2; see
# tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# These twelve complete upstream methods retain every input and assertion; only
# unittest scaffolding becomes tables and ordinary assertions. No input sizes or
# Unicode results are normalized. Platform expectations still use os.path.normcase.
# Two additional methods are partial: test_filter omits its bytes assertion, and
# test_warnings retains matches but cannot test the unsupported warnings machinery.
# Three bytes/mixed-type methods are unsupported. No partial method counts as fully
# compiled. The .out is recorded with CPython's stdlib; JIT/AOT use lib/fnmatch.
from fnmatch import fnmatch, fnmatchcase, translate, filter
import os
import re
import string


# test_fnmatch.FnmatchTestCase.test_fnmatch
def test_fnmatch() -> None:
    cases = [
        ('abc', 'abc', True), ('abc', '?*?', True), ('abc', '???*', True),
        ('abc', '*???', True), ('abc', '???', True), ('abc', '*', True),
        ('abc', 'ab[cd]', True), ('abc', 'ab[!de]', True),
        ('abc', 'ab[de]', False), ('a', '??', False), ('a', 'b', False),
        ('\\', r'[\]', True), ('a', r'[!\]', True), ('\\', r'[!\]', False),
        ('foo\nbar', 'foo*', True), ('foo\nbar\n', 'foo*', True),
        ('\nfoo', 'foo*', False), ('\n', '*', True),
    ]
    for name, pattern, expected in cases:
        assert fnmatch(name, pattern) == expected
    print('FnmatchTestCase.test_fnmatch', len(cases))


# test_fnmatch.FnmatchTestCase.test_slow_fnmatch
def test_slow_fnmatch() -> None:
    assert fnmatch('a' * 50, '*a*a*a*a*a*a*a*a*a*a')
    assert not fnmatch('a' * 50 + 'b', '*a*a*a*a*a*a*a*a*a*a')
    print('FnmatchTestCase.test_slow_fnmatch', 2)


# test_fnmatch.FnmatchTestCase.test_fnmatchcase
def test_fnmatchcase() -> None:
    cases = [
        ('abc', 'abc', True), ('AbC', 'abc', False),
        ('abc', 'AbC', False), ('AbC', 'AbC', True),
        ('usr/bin', 'usr/bin', True), ('usr\\bin', 'usr/bin', False),
        ('usr/bin', 'usr\\bin', False), ('usr\\bin', 'usr\\bin', True),
    ]
    for name, pattern, expected in cases:
        assert fnmatchcase(name, pattern) == expected
    print('FnmatchTestCase.test_fnmatchcase', len(cases))


# test_fnmatch.TranslateTestCase.test_translate
def test_translate() -> None:
    cases = [
        ('*', r'(?s:.*)\Z'), ('?', r'(?s:.)\Z'),
        ('a?b*', r'(?s:a.b.*)\Z'), ('[abc]', r'(?s:[abc])\Z'),
        ('[]]', r'(?s:[]])\Z'), ('[!x]', r'(?s:[^x])\Z'),
        ('[^x]', r'(?s:[\^x])\Z'), ('[x', r'(?s:\[x)\Z'),
        ('*.txt', r'(?s:.*\.txt)\Z'), ('*********', r'(?s:.*)\Z'),
        ('A*********', r'(?s:A.*)\Z'), ('*********A', r'(?s:.*A)\Z'),
        ('A*********?[?]?', r'(?s:A.*.[?].)\Z'),
        ('**a*a****a', r'(?s:(?>.*?a)(?>.*?a).*a)\Z'),
    ]
    for pattern, expected in cases:
        assert translate(pattern) == expected
    fatre = '|'.join([translate('**a**a**a*'), translate('**b**b**b*'),
                     translate('*c*c*c*')])
    assert re.match(fatre, 'abaccad') is not None
    assert re.match(fatre, 'abxbcab') is not None
    assert re.match(fatre, 'cbabcaxc') is not None
    assert re.match(fatre, 'dabccbad') is None
    print('TranslateTestCase.test_translate', len(cases) + 4)


def check(filename: str, pattern: str, should_match: bool = True) -> None:
    assert fnmatch(filename, pattern) == should_match


# test_fnmatch.FnmatchTestCase.test_case
def test_case() -> None:
    ignorecase = os.path.normcase('ABC') == os.path.normcase('abc')
    check('abc', 'abc')
    check('AbC', 'abc', ignorecase)
    check('abc', 'AbC', ignorecase)
    check('AbC', 'AbC')
    print('FnmatchTestCase.test_case')


# test_fnmatch.FnmatchTestCase.test_sep
def test_sep() -> None:
    normsep = os.path.normcase('\\') == os.path.normcase('/')
    check('usr/bin', 'usr/bin')
    check('usr\\bin', 'usr/bin', normsep)
    check('usr/bin', 'usr\\bin', normsep)
    check('usr\\bin', 'usr\\bin')
    print('FnmatchTestCase.test_sep')


# test_fnmatch.FnmatchTestCase.test_char_set
def test_char_set() -> None:
    ignorecase = os.path.normcase('ABC') == os.path.normcase('abc')
    tescases = string.ascii_lowercase + string.digits + string.punctuation
    for c in tescases:
        check(c, '[az]', c in 'az')
        check(c, '[!az]', c not in 'az')
    # Case insensitive.
    for c in tescases:
        check(c, '[AZ]', (c in 'az') and ignorecase)
        check(c, '[!AZ]', (c not in 'az') or not ignorecase)
    for c in string.ascii_uppercase:
        check(c, '[az]', (c in 'AZ') and ignorecase)
        check(c, '[!az]', (c not in 'AZ') or not ignorecase)
    # Repeated same character.
    for c in tescases:
        check(c, '[aa]', c == 'a')
    # Special cases.
    for c in tescases:
        check(c, '[^az]', c in '^az')
        check(c, '[[az]', c in '[az')
        check(c, r'[!]]', c != ']')
    check('[', '[')
    check('[]', '[]')
    check('[!', '[!')
    check('[!]', '[!]')
    print('FnmatchTestCase.test_char_set')


# test_fnmatch.FnmatchTestCase.test_range
def test_range() -> None:
    ignorecase = os.path.normcase('ABC') == os.path.normcase('abc')
    normsep = os.path.normcase('\\') == os.path.normcase('/')
    tescases = string.ascii_lowercase + string.digits + string.punctuation
    for c in tescases:
        check(c, '[b-d]', c in 'bcd')
        check(c, '[!b-d]', c not in 'bcd')
        check(c, '[b-dx-z]', c in 'bcdxyz')
        check(c, '[!b-dx-z]', c not in 'bcdxyz')
    # Case insensitive.
    for c in tescases:
        check(c, '[B-D]', (c in 'bcd') and ignorecase)
        check(c, '[!B-D]', (c not in 'bcd') or not ignorecase)
    for c in string.ascii_uppercase:
        check(c, '[b-d]', (c in 'BCD') and ignorecase)
        check(c, '[!b-d]', (c not in 'BCD') or not ignorecase)
    # Upper bound == lower bound.
    for c in tescases:
        check(c, '[b-b]', c == 'b')
    # Special cases.
    for c in tescases:
        check(c, '[!-#]', c not in '-#')
        check(c, '[!--.]', c not in '-.')
        check(c, '[^-`]', c in '^_`')
        if not (normsep and c == '/'):
            check(c, '[[-^]', c in r'[\]^')
            check(c, r'[\-^]', c in r'\]^')
        check(c, '[b-]', c in '-b')
        check(c, '[!b-]', c not in '-b')
        check(c, '[-b]', c in '-b')
        check(c, '[!-b]', c not in '-b')
        check(c, '[-]', c in '-')
        check(c, '[!-]', c not in '-')
    # Upper bound is less than lower bound: error in RE.
    for c in tescases:
        check(c, '[d-b]', False)
        check(c, '[!d-b]', True)
        check(c, '[d-bx-z]', c in 'xyz')
        check(c, '[!d-bx-z]', c not in 'xyz')
        check(c, '[d-b^-`]', c in '^_`')
        if not (normsep and c == '/'):
            check(c, '[d-b[-^]', c in r'[\]^')
    print('FnmatchTestCase.test_range')


# test_fnmatch.FnmatchTestCase.test_sep_in_char_set
def test_sep_in_char_set() -> None:
    normsep = os.path.normcase('\\') == os.path.normcase('/')
    check('/', r'[/]')
    check('\\', r'[\]')
    check('/', r'[\]', normsep)
    check('\\', r'[/]', normsep)
    check('[/]', r'[/]', False)
    check(r'[\\]', r'[/]', False)
    check('\\', r'[\t]')
    check('/', r'[\t]', normsep)
    check('t', r'[\t]')
    check('\t', r'[\t]', False)
    print('FnmatchTestCase.test_sep_in_char_set')


# test_fnmatch.FnmatchTestCase.test_sep_in_range
def test_sep_in_range() -> None:
    normsep = os.path.normcase('\\') == os.path.normcase('/')
    check('a/b', 'a[.-0]b', not normsep)
    check('a\\b', 'a[.-0]b', False)
    check('a\\b', 'a[Z-^]b', not normsep)
    check('a/b', 'a[Z-^]b', False)
    check('a/b', 'a[/-0]b', not normsep)
    check(r'a\b', 'a[/-0]b', False)
    check('a[/-0]b', 'a[/-0]b', False)
    check(r'a[\-0]b', 'a[/-0]b', False)
    check('a/b', 'a[.-/]b')
    check(r'a\b', 'a[.-/]b', normsep)
    check('a[.-/]b', 'a[.-/]b', False)
    check(r'a[.-\]b', 'a[.-/]b', False)
    check(r'a\b', r'a[\-^]b')
    check('a/b', r'a[\-^]b', normsep)
    check(r'a[\-^]b', r'a[\-^]b', False)
    check('a[/-^]b', r'a[\-^]b', False)
    check(r'a\b', r'a[Z-\]b', not normsep)
    check('a/b', r'a[Z-\]b', False)
    check(r'a[Z-\]b', r'a[Z-\]b', False)
    check('a[Z-/]b', r'a[Z-\]b', False)
    print('FnmatchTestCase.test_sep_in_range')


# test_fnmatch.FilterTestCase.test_case
def test_filter_case() -> None:
    ignorecase = os.path.normcase('P') == os.path.normcase('p')
    assert filter(['Test.py', 'Test.rb', 'Test.PL'], '*.p*') == (
        ['Test.py', 'Test.PL'] if ignorecase else ['Test.py'])
    assert filter(['Test.py', 'Test.rb', 'Test.PL'], '*.P*') == (
        ['Test.py', 'Test.PL'] if ignorecase else ['Test.PL'])
    print('FilterTestCase.test_case')


# test_fnmatch.FilterTestCase.test_sep
def test_filter_sep() -> None:
    normsep = os.path.normcase('\\') == os.path.normcase('/')
    assert filter(['usr/bin', 'usr', 'usr\\lib'], 'usr/*') == (
        ['usr/bin', 'usr\\lib'] if normsep else ['usr/bin'])
    assert filter(['usr/bin', 'usr', 'usr\\lib'], 'usr\\*') == (
        ['usr/bin', 'usr\\lib'] if normsep else ['usr\\lib'])
    print('FilterTestCase.test_sep')


# test_fnmatch.FnmatchTestCase.test_warnings
# PARTIAL: warning capture is unsupported.
# All six matches are retained; warnings.catch_warnings/simplefilter are unsupported.
def test_warnings_partial() -> None:
    check('[', '[[]')
    check('&', '[a&&b]')
    check('|', '[a||b]')
    check('~', '[a~~b]')
    check(',', '[a-z+--A-Z]')
    check('.', '[a-z--/A-Z]')
    print('PARTIAL FnmatchTestCase.test_warnings (matches only)')


# test_fnmatch.FilterTestCase.test_filter
# PARTIAL: bytes filtering is unsupported.
# The str assertion is retained; the bytes assertion is outside the port's scope.
def test_filter_partial() -> None:
    assert filter(['Python', 'Ruby', 'Perl', 'Tcl'], 'P*') == ['Python', 'Perl']
    print('PARTIAL FilterTestCase.test_filter (str only)')


test_fnmatch()
test_slow_fnmatch()
test_fnmatchcase()
test_translate()
test_case()
test_sep()
test_char_set()
test_range()
test_sep_in_char_set()
test_sep_in_range()
test_filter_case()
test_filter_sep()
test_warnings_partial()
test_filter_partial()
