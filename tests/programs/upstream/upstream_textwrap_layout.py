# Adapted from CPython 3.13.16 Lib/test/test_textwrap.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91: every test method of MaxLinesTestCase,
# LongWordTestCase, LongWordWithHyphensTestCase and IndentTestCases (13 complete methods
# and one adapted method, recorded as partial coverage in the manifest).
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each method is a function, with its class attribute or setUp values initialized per call.
# BaseTestCase.check/check_wrap become plain helpers that print and assert the same values;
# assertRaises becomes try/except/else. No original inputs or expected values are omitted.
# IndentTestCases.test_initial_indent uses new names when lists become strings, as a variable
# has one type. PASS lines identify exactly which original methods completed.
# test_nobreak_long specializes its fresh wrapper with break_long_words=0 before the original
# assignment of 0: assigning int 0 to a field initialized to bool True is rejected. No operation
# uses that field before the assignment upstream; both original 0 arguments and assertions stay.
from textwrap import TextWrapper, fill, wrap

def check(result, expect) -> None:
    print(result)
    assert result == expect

def check_wrap(text, width, expect, **kwargs) -> None:
    check(wrap(text, width, **kwargs), expect)

# test_textwrap.MaxLinesTestCase.test_simple
def MaxLinesTestCase_test_simple() -> None:
    text = "Hello there, how are you this fine day?  I'm glad to hear it!"
    check_wrap(text, 12, ['Hello [...]'], max_lines=0)
    check_wrap(text, 12, ['Hello [...]'], max_lines=1)
    check_wrap(text, 12, ['Hello there,', 'how [...]'], max_lines=2)
    check_wrap(text, 13, ['Hello there,', 'how are [...]'], max_lines=2)
    check_wrap(text, 80, [text], max_lines=1)
    check_wrap(text, 12, ['Hello there,', 'how are you', 'this fine', "day?  I'm", 'glad to hear', 'it!'], max_lines=6)

# test_textwrap.MaxLinesTestCase.test_spaces
def MaxLinesTestCase_test_spaces() -> None:
    text = "Hello there, how are you this fine day?  I'm glad to hear it!"
    check_wrap(text, 12, ['Hello there,', 'how are you', 'this fine', 'day? [...]'], max_lines=4)
    check_wrap(text, 6, ['Hello', '[...]'], max_lines=2)
    check_wrap(text + ' ' * 10, 12, ['Hello there,', 'how are you', 'this fine', "day?  I'm", 'glad to hear', 'it!'], max_lines=6)

# test_textwrap.MaxLinesTestCase.test_placeholder
def MaxLinesTestCase_test_placeholder() -> None:
    text = "Hello there, how are you this fine day?  I'm glad to hear it!"
    check_wrap(text, 12, ['Hello...'], max_lines=1, placeholder='...')
    check_wrap(text, 12, ['Hello there,', 'how are...'], max_lines=2, placeholder='...')
    try:
        wrap(text, 16, initial_indent='    ', max_lines=1, placeholder=' [truncated]...')
    except ValueError as error:
        print('ValueError', error)
    else:
        raise AssertionError('ValueError not raised')
    try:
        wrap(text, 16, subsequent_indent='    ', max_lines=2, placeholder=' [truncated]...')
    except ValueError as error:
        print('ValueError', error)
    else:
        raise AssertionError('ValueError not raised')
    check_wrap(text, 16, ['    Hello there,', '  [truncated]...'], max_lines=2, initial_indent='    ', subsequent_indent='  ', placeholder=' [truncated]...')
    check_wrap(text, 16, ['  [truncated]...'], max_lines=1, initial_indent='  ', subsequent_indent='    ', placeholder=' [truncated]...')
    check_wrap(text, 80, [text], placeholder='.' * 1000)

# test_textwrap.MaxLinesTestCase.test_placeholder_backtrack
def MaxLinesTestCase_test_placeholder_backtrack() -> None:
    text = "Hello there, how are you this fine day?  I'm glad to hear it!"
    text = 'Good grief Python features are advancing quickly!'
    check_wrap(text, 12, ['Good grief', 'Python*****'], max_lines=3, placeholder='*****')

# test_textwrap.LongWordTestCase.test_break_long
def LongWordTestCase_test_break_long() -> None:
    wrapper = TextWrapper()
    text = 'Did you say "supercalifragilisticexpialidocious?"\nHow *do* you spell that odd word, anyways?\n'
    check_wrap(text, 30, ['Did you say "supercalifragilis', 'ticexpialidocious?" How *do*', 'you spell that odd word,', 'anyways?'])
    check_wrap(text, 50, ['Did you say "supercalifragilisticexpialidocious?"', 'How *do* you spell that odd word, anyways?'])
    check_wrap('-' * 10 + 'hello', 10, ['----------', '               h', '               e', '               l', '               l', '               o'], subsequent_indent=' ' * 15)
    check_wrap(text, 12, ['Did you say', '"supercalifr', 'agilisticexp', 'ialidocious?', '" How *do*', 'you spell', 'that odd', 'word,', 'anyways?'])

# test_textwrap.LongWordTestCase.test_nobreak_long
def LongWordTestCase_test_nobreak_long() -> None:
    wrapper = TextWrapper(break_long_words=0)
    text = 'Did you say "supercalifragilisticexpialidocious?"\nHow *do* you spell that odd word, anyways?\n'
    wrapper.break_long_words = 0
    wrapper.width = 30
    expect = ['Did you say', '"supercalifragilisticexpialidocious?"', 'How *do* you spell that odd', 'word, anyways?']
    result = wrapper.wrap(text)
    check(result, expect)
    result = wrap(text, width=30, break_long_words=0)
    check(result, expect)

# test_textwrap.LongWordTestCase.test_max_lines_long
def LongWordTestCase_test_max_lines_long() -> None:
    wrapper = TextWrapper()
    text = 'Did you say "supercalifragilisticexpialidocious?"\nHow *do* you spell that odd word, anyways?\n'
    check_wrap(text, 12, ['Did you say', '"supercalifr', 'agilisticexp', '[...]'], max_lines=4)

# test_textwrap.LongWordWithHyphensTestCase.test_break_long_words_on_hyphen
def LongWordWithHyphensTestCase_test_break_long_words_on_hyphen() -> None:
    wrapper = TextWrapper()
    text1 = 'We used enyzme 2-succinyl-6-hydroxy-2,4-cyclohexadiene-1-carboxylate synthase.\n'
    text2 = '1234567890-1234567890--this_is_a_very_long_option_indeed-good-bye"\n'
    expected = ['We used enyzme 2-succinyl-6-hydroxy-2,4-', 'cyclohexadiene-1-carboxylate synthase.']
    check_wrap(text1, 50, expected)
    expected = ['We used', 'enyzme 2-', 'succinyl-', '6-hydroxy-', '2,4-', 'cyclohexad', 'iene-1-', 'carboxylat', 'e', 'synthase.']
    check_wrap(text1, 10, expected)
    expected = ['1234567890', '-123456789', '0--this_is', '_a_very_lo', 'ng_option_', 'indeed-', 'good-bye"']
    check_wrap(text2, 10, expected)

# test_textwrap.LongWordWithHyphensTestCase.test_break_long_words_not_on_hyphen
def LongWordWithHyphensTestCase_test_break_long_words_not_on_hyphen() -> None:
    wrapper = TextWrapper()
    text1 = 'We used enyzme 2-succinyl-6-hydroxy-2,4-cyclohexadiene-1-carboxylate synthase.\n'
    text2 = '1234567890-1234567890--this_is_a_very_long_option_indeed-good-bye"\n'
    expected = ['We used enyzme 2-succinyl-6-hydroxy-2,4-cyclohexad', 'iene-1-carboxylate synthase.']
    check_wrap(text1, 50, expected, break_on_hyphens=False)
    expected = ['We used', 'enyzme 2-s', 'uccinyl-6-', 'hydroxy-2,', '4-cyclohex', 'adiene-1-c', 'arboxylate', 'synthase.']
    check_wrap(text1, 10, expected, break_on_hyphens=False)
    expected = ['1234567890', '-123456789', '0--this_is', '_a_very_lo', 'ng_option_', 'indeed-', 'good-bye"']
    check_wrap(text2, 10, expected)

# test_textwrap.LongWordWithHyphensTestCase.test_break_on_hyphen_but_not_long_words
def LongWordWithHyphensTestCase_test_break_on_hyphen_but_not_long_words() -> None:
    wrapper = TextWrapper()
    text1 = 'We used enyzme 2-succinyl-6-hydroxy-2,4-cyclohexadiene-1-carboxylate synthase.\n'
    text2 = '1234567890-1234567890--this_is_a_very_long_option_indeed-good-bye"\n'
    expected = ['We used enyzme', '2-succinyl-6-hydroxy-2,4-cyclohexadiene-1-carboxylate', 'synthase.']
    check_wrap(text1, 50, expected, break_long_words=False)
    expected = ['We used', 'enyzme', '2-succinyl-6-hydroxy-2,4-cyclohexadiene-1-carboxylate', 'synthase.']
    check_wrap(text1, 10, expected, break_long_words=False)
    expected = ['1234567890', '-123456789', '0--this_is', '_a_very_lo', 'ng_option_', 'indeed-', 'good-bye"']
    check_wrap(text2, 10, expected)

# test_textwrap.LongWordWithHyphensTestCase.test_do_not_break_long_words_or_on_hyphens
def LongWordWithHyphensTestCase_test_do_not_break_long_words_or_on_hyphens() -> None:
    wrapper = TextWrapper()
    text1 = 'We used enyzme 2-succinyl-6-hydroxy-2,4-cyclohexadiene-1-carboxylate synthase.\n'
    text2 = '1234567890-1234567890--this_is_a_very_long_option_indeed-good-bye"\n'
    expected = ['We used enyzme', '2-succinyl-6-hydroxy-2,4-cyclohexadiene-1-carboxylate', 'synthase.']
    check_wrap(text1, 50, expected, break_long_words=False, break_on_hyphens=False)
    expected = ['We used', 'enyzme', '2-succinyl-6-hydroxy-2,4-cyclohexadiene-1-carboxylate', 'synthase.']
    check_wrap(text1, 10, expected, break_long_words=False, break_on_hyphens=False)
    expected = ['1234567890', '-123456789', '0--this_is', '_a_very_lo', 'ng_option_', 'indeed-', 'good-bye"']
    check_wrap(text2, 10, expected)

# test_textwrap.IndentTestCases.test_fill
def IndentTestCases_test_fill() -> None:
    text = 'This paragraph will be filled, first without any indentation,\nand then with some (including a hanging indent).'
    expect = 'This paragraph will be filled, first\nwithout any indentation, and then with\nsome (including a hanging indent).'
    result = fill(text, 40)
    check(result, expect)

# test_textwrap.IndentTestCases.test_initial_indent
def IndentTestCases_test_initial_indent() -> None:
    text = 'This paragraph will be filled, first without any indentation,\nand then with some (including a hanging indent).'
    expect = ['     This paragraph will be filled,', 'first without any indentation, and then', 'with some (including a hanging indent).']
    result = wrap(text, 40, initial_indent='     ')
    check(result, expect)
    expect_str = '\n'.join(expect)
    result_str = fill(text, 40, initial_indent='     ')
    check(result_str, expect_str)

# test_textwrap.IndentTestCases.test_subsequent_indent
def IndentTestCases_test_subsequent_indent() -> None:
    text = 'This paragraph will be filled, first without any indentation,\nand then with some (including a hanging indent).'
    expect = '  * This paragraph will be filled, first\n    without any indentation, and then\n    with some (including a hanging\n    indent).'
    result = fill(text, 40, initial_indent='  * ', subsequent_indent='    ')
    check(result, expect)
MaxLinesTestCase_test_simple()
print('PASS test_textwrap.MaxLinesTestCase.test_simple')
MaxLinesTestCase_test_spaces()
print('PASS test_textwrap.MaxLinesTestCase.test_spaces')
MaxLinesTestCase_test_placeholder()
print('PASS test_textwrap.MaxLinesTestCase.test_placeholder')
MaxLinesTestCase_test_placeholder_backtrack()
print('PASS test_textwrap.MaxLinesTestCase.test_placeholder_backtrack')
LongWordTestCase_test_break_long()
print('PASS test_textwrap.LongWordTestCase.test_break_long')
LongWordTestCase_test_nobreak_long()
print('PASS adapted test_textwrap.LongWordTestCase.test_nobreak_long')
LongWordTestCase_test_max_lines_long()
print('PASS test_textwrap.LongWordTestCase.test_max_lines_long')
LongWordWithHyphensTestCase_test_break_long_words_on_hyphen()
print('PASS test_textwrap.LongWordWithHyphensTestCase.test_break_long_words_on_hyphen')
LongWordWithHyphensTestCase_test_break_long_words_not_on_hyphen()
print('PASS test_textwrap.LongWordWithHyphensTestCase.test_break_long_words_not_on_hyphen')
LongWordWithHyphensTestCase_test_break_on_hyphen_but_not_long_words()
print('PASS test_textwrap.LongWordWithHyphensTestCase.test_break_on_hyphen_but_not_long_words')
LongWordWithHyphensTestCase_test_do_not_break_long_words_or_on_hyphens()
print('PASS test_textwrap.LongWordWithHyphensTestCase.test_do_not_break_long_words_or_on_hyphens')
IndentTestCases_test_fill()
print('PASS test_textwrap.IndentTestCases.test_fill')
IndentTestCases_test_initial_indent()
print('PASS test_textwrap.IndentTestCases.test_initial_indent')
IndentTestCases_test_subsequent_indent()
print('PASS test_textwrap.IndentTestCases.test_subsequent_indent')
