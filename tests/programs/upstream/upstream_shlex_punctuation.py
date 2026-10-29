# Adapted from CPython 3.13.16 Lib/test/test_shlex.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91, SHA-256
# 943ddf74ffa1da625169221d17e84f386314016da36bc3696ebcdb9ca88b039d.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Complete ShlexTest methods: testSyntaxSplitAmpersandAndPipe, testSyntaxSplitSemicolon,
# testSyntaxSplitRedirect, testSyntaxSplitParen, testSyntaxSplitCustom, testTokenTypes,
# testPunctuationInWordChars, testPunctuationWithWhitespaceSplit, testPunctuationWithPosix,
# testEmptyStringHandling, testUnicodeHandling, testQuote, testJoin, testLinenoAfterNewLine,
# testLinenoAfterComment, testPushToken, testPushTokenLifo, testPushSourceString,
# testPushSourceStream, testErrorLeaderTracksPosition, testErrorLeaderOverrides,
# testNoClosingQuotation and testNoEscapedCharacter. Every input and assertion is kept;
# unittest scaffolding becomes functions, assertions and printed results. subTest
# becomes a loop. Debug-output methods (unittest.mock), file/sourcehook methods and
# testPunctuationCharsReadOnly are not included. testCompat, testSplitPosix and
# testJoinRoundtrip are in tests/programs/library/lib_shlex_upstream.py.
# One adaptation: testTokenTypes adds `t is None` to its EOF test, because comparing
# with s.eof does not narrow get_token()'s str | None result. Non-POSIX shlex returns
# '' at EOF, so the guard never fires and behaviour is unchanged.
import io
import itertools
import shlex
import string


def split_all(ss: str, ws: bool) -> list[str]:
    s = shlex.shlex(ss, punctuation_chars=True)
    s.whitespace_split = ws
    return list(s)


def test_syntax_split_ampersand_and_pipe() -> None:
    for delimiter in ('&&', '&', '|&', ';&', ';;&',
                      '||', '|', '&|', ';|', ';;|'):
        src = ['echo hi %s echo bye' % delimiter,
               'echo hi%secho bye' % delimiter]
        ref = ['echo', 'hi', delimiter, 'echo', 'bye']
        for ss, ws in itertools.product(src, (False, True)):
            result = split_all(ss, ws)
            assert ref == result, "While splitting '%s' [ws=%s]" % (ss, ws)
    print('ampersand and pipe ok')


def test_syntax_split_semicolon() -> None:
    for delimiter in (';', ';;', ';&', ';;&'):
        src = ['echo hi %s echo bye' % delimiter,
               'echo hi%s echo bye' % delimiter,
               'echo hi%secho bye' % delimiter]
        ref = ['echo', 'hi', delimiter, 'echo', 'bye']
        for ss, ws in itertools.product(src, (False, True)):
            result = split_all(ss, ws)
            assert ref == result, "While splitting '%s' [ws=%s]" % (ss, ws)
    print('semicolon ok')


def test_syntax_split_redirect() -> None:
    for delimiter in ('<', '|'):
        src = ['echo hi %s out' % delimiter,
               'echo hi%s out' % delimiter,
               'echo hi%sout' % delimiter]
        ref = ['echo', 'hi', delimiter, 'out']
        for ss, ws in itertools.product(src, (False, True)):
            # Upstream never sets whitespace_split here; ws only labels the message.
            s = shlex.shlex(ss, punctuation_chars=True)
            result = list(s)
            assert ref == result, "While splitting '%s' [ws=%s]" % (ss, ws)
    print('redirect ok')


def test_syntax_split_paren() -> None:
    src = ['( echo hi )',
           '(echo hi)']
    ref = ['(', 'echo', 'hi', ')']
    for ss, ws in itertools.product(src, (False, True)):
        result = split_all(ss, ws)
        assert ref == result, "While splitting '%s' [ws=%s]" % (ss, ws)
    print('paren ok')


def test_syntax_split_custom() -> None:
    ss = "~/a&&b-c --color=auto||d *.py?"
    ref = ['~/a', '&', '&', 'b-c', '--color=auto', '||', 'd', '*.py?']
    s = shlex.shlex(ss, punctuation_chars="|")
    result = list(s)
    assert ref == result, "While splitting '%s' [ws=False]" % ss
    ref = ['~/a&&b-c', '--color=auto', '||', 'd', '*.py?']
    s = shlex.shlex(ss, punctuation_chars="|")
    s.whitespace_split = True
    result = list(s)
    assert ref == result, "While splitting '%s' [ws=True]" % ss
    print('custom', result)


def test_token_types() -> None:
    for source, expected in (
            ('a && b || c',
             [('a', 'a'), ('&&', 'c'), ('b', 'a'),
              ('||', 'c'), ('c', 'a')]),
    ):
        s = shlex.shlex(source, punctuation_chars=True)
        observed: list[tuple[str, str]] = []
        while True:
            t = s.get_token()
            if t is None or t == s.eof:  # added guard: narrows get_token()'s str | None
                break
            if t[0] in s.punctuation_chars:
                tt = 'c'
            else:
                tt = 'a'
            observed.append((t, tt))
        assert observed == expected
        print('token types', observed)


def test_punctuation_in_word_chars() -> None:
    s = shlex.shlex('a_b__c', punctuation_chars='_')
    assert '_' not in s.wordchars
    result = list(s)
    assert result == ['a', '_', 'b', '__', 'c']
    print('punctuation in wordchars', result)


def test_punctuation_with_whitespace_split() -> None:
    s = shlex.shlex('a  && b  ||  c', punctuation_chars='&')
    assert list(s) == ['a', '&&', 'b', '|', '|', 'c']
    s = shlex.shlex('a  && b  ||  c', punctuation_chars='&')
    s.whitespace_split = True
    assert list(s) == ['a', '&&', 'b', '||', 'c']
    print('punctuation with whitespace_split ok')


def test_punctuation_with_posix() -> None:
    s = shlex.shlex('f >"abc"', posix=True, punctuation_chars=True)
    assert list(s) == ['f', '>', 'abc']
    s = shlex.shlex('f >\\"abc\\"', posix=True, punctuation_chars=True)
    assert list(s) == ['f', '>', '"abc"']
    print('punctuation with posix ok')


def test_empty_string_handling() -> None:
    expected = ['', ')', 'abc']
    for punct in (False, True):
        s = shlex.shlex("'')abc", posix=True, punctuation_chars=punct)
        slist = list(s)
        assert slist == expected
    expected = ["''", ')', 'abc']
    s = shlex.shlex("'')abc", punctuation_chars=True)
    assert list(s) == expected
    print('empty string ok')


def test_unicode_handling() -> None:
    ss = "ℙƴ☂ℌøἤ"
    ref = ['ℙƴ☂ℌøἤ']
    s = shlex.shlex(ss, punctuation_chars=True)
    s.whitespace_split = True
    assert list(s) == ref
    ref = ['ℙ', 'ƴ', '☂', 'ℌ', 'ø', 'ἤ']
    s = shlex.shlex(ss, punctuation_chars=True)
    assert list(s) == ref
    print('unicode', ref)


def test_quote() -> None:
    safeunquoted = string.ascii_letters + string.digits + '@%_-+=:,./'
    unicode_sample = '\xe9\xe0\xdf'  # e + acute accent, a + grave, sharp s
    unsafe = '"`$\\!' + unicode_sample

    assert shlex.quote('') == "''"
    assert shlex.quote(safeunquoted) == safeunquoted
    assert shlex.quote('test file name') == "'test file name'"
    for u in unsafe:
        assert shlex.quote('test%sname' % u) == "'test%sname'" % u
    for u in unsafe:
        assert shlex.quote("test%s'name'" % u) == "'test%s'\"'\"'name'\"'\"''" % u
    print('quote', shlex.quote("test$'name'"))


def test_join() -> None:
    for split_command, command in [
        (['a ', 'b'], "'a ' b"),
        (['a', ' b'], "a ' b'"),
        (['a', ' ', 'b'], "a ' ' b"),
        (['"a', 'b"'], '\'"a\' \'b"\''),
    ]:
        joined = shlex.join(split_command)
        assert joined == command, command
        print('join', joined)


def test_lineno() -> None:
    s = shlex.shlex("line 1\nline 2")
    assert s.lineno == 1  # before consumption
    list(s)
    assert s.lineno == 2
    s = shlex.shlex("line 1 # line 2")
    list(s)
    assert s.lineno == 2
    print('lineno ok')


def test_push() -> None:
    s = shlex.shlex("b c")
    s.push_token("a")
    assert list(s) == ["a", "b", "c"]
    s = shlex.shlex("")
    s.push_token("first")
    s.push_token("last")
    assert list(s) == ["last", "first"]
    s = shlex.shlex("world")
    s.push_source("hello")
    assert list(s) == ["hello", "world"]
    s = shlex.shlex("world")
    s.push_source(io.StringIO("hello"))
    assert list(s) == ["hello", "world"]
    print('push ok')


def test_error_leader() -> None:
    infile_label = "test.sh"
    s = shlex.shlex("line 1\nline 2", infile=infile_label)
    list(s)
    result = s.error_leader()
    assert result == f'"{infile_label}", line 2: '
    s = shlex.shlex("foo", infile="original.sh")
    infile_label_override = "override.sh"
    lineno_override = 42
    result = s.error_leader(infile=infile_label_override, lineno=lineno_override)
    assert result == f'"{infile_label_override}", line {lineno_override}: '
    print('error leader', result)


def test_errors() -> None:
    s = shlex.shlex('"foo')
    try:
        list(s)
        assert False, 'no error'
    except ValueError as e:
        assert "No closing quotation" in str(e)
        print('ValueError', e)
    s = shlex.shlex("\\", posix=True)
    try:
        list(s)
        assert False, 'no error'
    except ValueError as e:
        assert "No escaped character" in str(e)
        print('ValueError', e)


test_syntax_split_ampersand_and_pipe()
test_syntax_split_semicolon()
test_syntax_split_redirect()
test_syntax_split_paren()
test_syntax_split_custom()
test_token_types()
test_punctuation_in_word_chars()
test_punctuation_with_whitespace_split()
test_punctuation_with_posix()
test_empty_string_handling()
test_unicode_handling()
test_quote()
test_join()
test_lineno()
test_push()
test_error_leader()
test_errors()
