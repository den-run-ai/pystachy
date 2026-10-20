# Adapted from CPython 3.13.16 Lib/test/test_textwrap.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91. PSF License v2; see
# tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# All 23 DedentTestCase, IndentTestCase and ShortenTestCase methods retain their
# complete upstream inputs and assertions. unittest classes/helpers become functions
# and assertions; assertRaises becomes try/except plus an assertion that it raised.
# No input sizes, Unicode results or expected values are normalized.
from textwrap import dedent, indent, shorten

# test_textwrap.DedentTestCase.test_dedent_nomargin
def DedentTestCase_test_dedent_nomargin() -> None:
    text = "Hello there.\nHow are you?\nOh good, I'm glad."
    assert dedent(text) == text
    text = 'Hello there.\n\nBoo!'
    assert dedent(text) == text
    text = 'Hello there.\n  This is indented.'
    assert dedent(text) == text
    text = 'Hello there.\n\n  Boo!\n'
    assert dedent(text) == text

# test_textwrap.DedentTestCase.test_dedent_even
def DedentTestCase_test_dedent_even() -> None:
    text = '  Hello there.\n  How are ya?\n  Oh good.'
    expect = 'Hello there.\nHow are ya?\nOh good.'
    assert expect == dedent(text)
    text = '  Hello there.\n\n  How are ya?\n  Oh good.\n'
    expect = 'Hello there.\n\nHow are ya?\nOh good.\n'
    assert expect == dedent(text)
    text = '  Hello there.\n  \n  How are ya?\n  Oh good.\n'
    expect = 'Hello there.\n\nHow are ya?\nOh good.\n'
    assert expect == dedent(text)

# test_textwrap.DedentTestCase.test_dedent_uneven
def DedentTestCase_test_dedent_uneven() -> None:
    text = '        def foo():\n            while 1:\n                return foo\n        '
    expect = 'def foo():\n    while 1:\n        return foo\n'
    assert expect == dedent(text)
    text = '  Foo\n    Bar\n\n   Baz\n'
    expect = 'Foo\n  Bar\n\n Baz\n'
    assert expect == dedent(text)
    text = '  Foo\n    Bar\n \n   Baz\n'
    expect = 'Foo\n  Bar\n\n Baz\n'
    assert expect == dedent(text)

# test_textwrap.DedentTestCase.test_dedent_declining
def DedentTestCase_test_dedent_declining() -> None:
    text = '     Foo\n    Bar\n'
    expect = ' Foo\nBar\n'
    assert expect == dedent(text)
    text = '     Foo\n\n    Bar\n'
    expect = ' Foo\n\nBar\n'
    assert expect == dedent(text)
    text = '     Foo\n    \n    Bar\n'
    expect = ' Foo\n\nBar\n'
    assert expect == dedent(text)

# test_textwrap.DedentTestCase.test_dedent_preserve_internal_tabs
def DedentTestCase_test_dedent_preserve_internal_tabs() -> None:
    text = '  hello\tthere\n  how are\tyou?'
    expect = 'hello\tthere\nhow are\tyou?'
    assert expect == dedent(text)
    assert expect == dedent(expect)

# test_textwrap.DedentTestCase.test_dedent_preserve_margin_tabs
def DedentTestCase_test_dedent_preserve_margin_tabs() -> None:
    text = '  hello there\n\thow are you?'
    assert dedent(text) == text
    text = '        hello there\n\thow are you?'
    assert dedent(text) == text
    text = '\thello there\n\thow are you?'
    expect = 'hello there\nhow are you?'
    assert expect == dedent(text)
    text = '  \thello there\n  \thow are you?'
    assert expect == dedent(text)
    text = '  \t  hello there\n  \t  how are you?'
    assert expect == dedent(text)
    text = '  \thello there\n  \t  how are you?'
    expect = 'hello there\n  how are you?'
    assert expect == dedent(text)
    text = "  \thello there\n   \thow are you?\n \tI'm fine, thanks"
    expect = " \thello there\n  \thow are you?\n\tI'm fine, thanks"
    assert expect == dedent(text)

ROUNDTRIP_CASES = ('Hi.\nThis is a test.\nTesting.', 'Hi.\nThis is a test.\n\nTesting.', '\nHi.\nThis is a test.\nTesting.\n')

CASES = ROUNDTRIP_CASES + ('Hi.\r\nThis is a test.\r\nTesting.\r\n', '\nHi.\r\nThis is a test.\n\r\nTesting.\r\n\n')

# test_textwrap.IndentTestCase.test_indent_nomargin_default
def IndentTestCase_test_indent_nomargin_default() -> None:
    for text in CASES:
        assert indent(text, '') == text

# test_textwrap.IndentTestCase.test_indent_nomargin_explicit_default
def IndentTestCase_test_indent_nomargin_explicit_default() -> None:
    for text in CASES:
        assert indent(text, '', None) == text

# test_textwrap.IndentTestCase.test_indent_nomargin_all_lines
def IndentTestCase_test_indent_nomargin_all_lines() -> None:
    predicate = lambda line: True
    for text in CASES:
        assert indent(text, '', predicate) == text

# test_textwrap.IndentTestCase.test_indent_no_lines
def IndentTestCase_test_indent_no_lines() -> None:
    predicate = lambda line: False
    for text in CASES:
        assert indent(text, '    ', predicate) == text

# test_textwrap.IndentTestCase.test_roundtrip_spaces
def IndentTestCase_test_roundtrip_spaces() -> None:
    for text in ROUNDTRIP_CASES:
        assert dedent(indent(text, '    ')) == text

# test_textwrap.IndentTestCase.test_roundtrip_tabs
def IndentTestCase_test_roundtrip_tabs() -> None:
    for text in ROUNDTRIP_CASES:
        assert dedent(indent(text, '\t\t')) == text

# test_textwrap.IndentTestCase.test_roundtrip_mixed
def IndentTestCase_test_roundtrip_mixed() -> None:
    for text in ROUNDTRIP_CASES:
        assert dedent(indent(text, ' \t  \t ')) == text

# test_textwrap.IndentTestCase.test_indent_default
def IndentTestCase_test_indent_default() -> None:
    prefix = '  '
    expected = ('  Hi.\n  This is a test.\n  Testing.', '  Hi.\n  This is a test.\n\n  Testing.', '\n  Hi.\n  This is a test.\n  Testing.\n', '  Hi.\r\n  This is a test.\r\n  Testing.\r\n', '\n  Hi.\r\n  This is a test.\n\r\n  Testing.\r\n\n')
    for text, expect in zip(CASES, expected):
        assert indent(text, prefix) == expect

# test_textwrap.IndentTestCase.test_indent_explicit_default
def IndentTestCase_test_indent_explicit_default() -> None:
    prefix = '  '
    expected = ('  Hi.\n  This is a test.\n  Testing.', '  Hi.\n  This is a test.\n\n  Testing.', '\n  Hi.\n  This is a test.\n  Testing.\n', '  Hi.\r\n  This is a test.\r\n  Testing.\r\n', '\n  Hi.\r\n  This is a test.\n\r\n  Testing.\r\n\n')
    for text, expect in zip(CASES, expected):
        assert indent(text, prefix, None) == expect

# test_textwrap.IndentTestCase.test_indent_all_lines
def IndentTestCase_test_indent_all_lines() -> None:
    prefix = '  '
    expected = ('  Hi.\n  This is a test.\n  Testing.', '  Hi.\n  This is a test.\n  \n  Testing.', '  \n  Hi.\n  This is a test.\n  Testing.\n', '  Hi.\r\n  This is a test.\r\n  Testing.\r\n', '  \n  Hi.\r\n  This is a test.\n  \r\n  Testing.\r\n  \n')
    predicate = lambda line: True
    for text, expect in zip(CASES, expected):
        assert indent(text, prefix, predicate) == expect

# test_textwrap.IndentTestCase.test_indent_empty_lines
def IndentTestCase_test_indent_empty_lines() -> None:
    prefix = '  '
    expected = ('Hi.\nThis is a test.\nTesting.', 'Hi.\nThis is a test.\n  \nTesting.', '  \nHi.\nThis is a test.\nTesting.\n', 'Hi.\r\nThis is a test.\r\nTesting.\r\n', '  \nHi.\r\nThis is a test.\n  \r\nTesting.\r\n  \n')
    predicate = lambda line: not line.strip()
    for text, expect in zip(CASES, expected):
        assert indent(text, prefix, predicate) == expect

# test_textwrap.ShortenTestCase.test_simple
def ShortenTestCase_test_simple() -> None:
    text = "Hello there, how are you this fine day? I'm glad to hear it!"
    assert shorten(text, 18) == 'Hello there, [...]'
    assert shorten(text, len(text)) == text
    assert shorten(text, len(text) - 1) == "Hello there, how are you this fine day? I'm glad to [...]"

# test_textwrap.ShortenTestCase.test_placeholder
def ShortenTestCase_test_placeholder() -> None:
    text = "Hello there, how are you this fine day? I'm glad to hear it!"
    assert shorten(text, 17, placeholder='$$') == 'Hello there,$$'
    assert shorten(text, 18, placeholder='$$') == 'Hello there, how$$'
    assert shorten(text, 18, placeholder=' $$') == 'Hello there, $$'
    assert shorten(text, len(text), placeholder='$$') == text
    assert shorten(text, len(text) - 1, placeholder='$$') == "Hello there, how are you this fine day? I'm glad to hear$$"

# test_textwrap.ShortenTestCase.test_empty_string
def ShortenTestCase_test_empty_string() -> None:
    assert shorten('', 6) == ''

# test_textwrap.ShortenTestCase.test_whitespace
def ShortenTestCase_test_whitespace() -> None:
    text = '\n            This is a  paragraph that  already has\n            line breaks and \t tabs too.'
    assert shorten(text, 62) == 'This is a paragraph that already has line breaks and tabs too.'
    assert shorten(text, 61) == 'This is a paragraph that already has line breaks and [...]'
    assert shorten('hello      world!  ', 12) == 'hello world!'
    assert shorten('hello      world!  ', 11) == 'hello [...]'
    assert shorten('hello      world!  ', 10) == '[...]'

# test_textwrap.ShortenTestCase.test_width_too_small_for_placeholder
def ShortenTestCase_test_width_too_small_for_placeholder() -> None:
    shorten('x' * 20, width=8, placeholder='(......)')
    caught = False
    try:
        shorten('x' * 20, width=8, placeholder='(.......)')
    except ValueError:
        caught = True
    assert caught

# test_textwrap.ShortenTestCase.test_first_word_too_long_but_placeholder_fits
def ShortenTestCase_test_first_word_too_long_but_placeholder_fits() -> None:
    assert shorten('Helloo', 5) == '[...]'

DedentTestCase_test_dedent_nomargin()
print('PASS test_textwrap.DedentTestCase.test_dedent_nomargin')
DedentTestCase_test_dedent_even()
print('PASS test_textwrap.DedentTestCase.test_dedent_even')
DedentTestCase_test_dedent_uneven()
print('PASS test_textwrap.DedentTestCase.test_dedent_uneven')
DedentTestCase_test_dedent_declining()
print('PASS test_textwrap.DedentTestCase.test_dedent_declining')
DedentTestCase_test_dedent_preserve_internal_tabs()
print('PASS test_textwrap.DedentTestCase.test_dedent_preserve_internal_tabs')
DedentTestCase_test_dedent_preserve_margin_tabs()
print('PASS test_textwrap.DedentTestCase.test_dedent_preserve_margin_tabs')
IndentTestCase_test_indent_nomargin_default()
print('PASS test_textwrap.IndentTestCase.test_indent_nomargin_default')
IndentTestCase_test_indent_nomargin_explicit_default()
print('PASS test_textwrap.IndentTestCase.test_indent_nomargin_explicit_default')
IndentTestCase_test_indent_nomargin_all_lines()
print('PASS test_textwrap.IndentTestCase.test_indent_nomargin_all_lines')
IndentTestCase_test_indent_no_lines()
print('PASS test_textwrap.IndentTestCase.test_indent_no_lines')
IndentTestCase_test_roundtrip_spaces()
print('PASS test_textwrap.IndentTestCase.test_roundtrip_spaces')
IndentTestCase_test_roundtrip_tabs()
print('PASS test_textwrap.IndentTestCase.test_roundtrip_tabs')
IndentTestCase_test_roundtrip_mixed()
print('PASS test_textwrap.IndentTestCase.test_roundtrip_mixed')
IndentTestCase_test_indent_default()
print('PASS test_textwrap.IndentTestCase.test_indent_default')
IndentTestCase_test_indent_explicit_default()
print('PASS test_textwrap.IndentTestCase.test_indent_explicit_default')
IndentTestCase_test_indent_all_lines()
print('PASS test_textwrap.IndentTestCase.test_indent_all_lines')
IndentTestCase_test_indent_empty_lines()
print('PASS test_textwrap.IndentTestCase.test_indent_empty_lines')
ShortenTestCase_test_simple()
print('PASS test_textwrap.ShortenTestCase.test_simple')
ShortenTestCase_test_placeholder()
print('PASS test_textwrap.ShortenTestCase.test_placeholder')
ShortenTestCase_test_empty_string()
print('PASS test_textwrap.ShortenTestCase.test_empty_string')
ShortenTestCase_test_whitespace()
print('PASS test_textwrap.ShortenTestCase.test_whitespace')
ShortenTestCase_test_width_too_small_for_placeholder()
print('PASS test_textwrap.ShortenTestCase.test_width_too_small_for_placeholder')
ShortenTestCase_test_first_word_too_long_but_placeholder_fits()
print('PASS test_textwrap.ShortenTestCase.test_first_word_too_long_but_placeholder_fits')
