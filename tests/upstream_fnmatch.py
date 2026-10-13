# Adapted from CPython 3.13.16 Lib/test/test_fnmatch.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91. PSF License v2; see
# tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# These four complete upstream methods retain every input and assertion; only
# unittest scaffolding becomes tables and ordinary assertions. No input sizes or
# Unicode results are normalized. Bytes and platform-dependent methods are not
# claimed here. The .out is recorded with CPython's stdlib; JIT/AOT use lib/fnmatch.
from fnmatch import fnmatch, fnmatchcase, translate
import re


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


test_fnmatch()
test_slow_fnmatch()
test_fnmatchcase()
test_translate()
