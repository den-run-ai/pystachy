# Adapted from CPython 3.13.16 Lib/test/test_textwrap.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91. PSF License v2; see
# tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# The 27 matching WrapTestCase methods preserve every input and assertion. unittest
# equality helpers become asserts, setUp creates a fresh wrapper where used, and
# assertRaises becomes try/except with a required catch. In test_whitespace,
# filled names the str result separately from the preceding list result.
# Two complete methods remain #120 deviations: test_umlaut_followed_by_dash and
# test_narrow_non_breaking_space. They are accounted for separately in the manifest.
from textwrap import TextWrapper, wrap


# test_textwrap.WrapTestCase.test_simple
def test_simple() -> None:
    text = "Hello there, how are you this fine day?  I'm glad to hear it!"
    assert wrap(text, 12) == ['Hello there,', 'how are you', 'this fine', "day?  I'm", 'glad to hear', 'it!']
    assert wrap(text, 42) == ['Hello there, how are you this fine day?', "I'm glad to hear it!"]
    assert wrap(text, 80) == [text]
    print('WrapTestCase.test_simple')


# test_textwrap.WrapTestCase.test_empty_string
def test_empty_string() -> None:
    assert wrap('', 6) == []
    assert wrap('', 6, drop_whitespace=False) == []
    print('WrapTestCase.test_empty_string')


# test_textwrap.WrapTestCase.test_empty_string_with_initial_indent
def test_empty_string_with_initial_indent() -> None:
    assert wrap('', 6, initial_indent='++') == []
    assert wrap('', 6, initial_indent='++', drop_whitespace=False) == []
    print('WrapTestCase.test_empty_string_with_initial_indent')


# test_textwrap.WrapTestCase.test_whitespace
def test_whitespace() -> None:
    text = 'This is a paragraph that already has\nline breaks.  But some of its lines are much longer than the others,\nso it needs to be wrapped.\nSome lines are \ttabbed too.\nWhat a mess!\n'
    expect = ['This is a paragraph that already has line', 'breaks.  But some of its lines are much', 'longer than the others, so it needs to be', 'wrapped.  Some lines are  tabbed too.  What a', 'mess!']
    wrapper = TextWrapper(45, fix_sentence_endings=True)
    result = wrapper.wrap(text)
    assert result == expect
    filled = wrapper.fill(text)
    assert filled == '\n'.join(expect)
    text = '\tTest\tdefault\t\ttabsize.'
    expect = ['        Test    default         tabsize.']
    assert wrap(text, 80) == expect
    text = '\tTest\tcustom\t\ttabsize.'
    expect = ['    Test    custom      tabsize.']
    assert wrap(text, 80, tabsize=4) == expect
    print('WrapTestCase.test_whitespace')


# test_textwrap.WrapTestCase.test_fix_sentence_endings
def test_fix_sentence_endings() -> None:
    wrapper = TextWrapper(60, fix_sentence_endings=True)
    text = 'A short line. Note the single space.'
    expect = ['A short line.  Note the single space.']
    assert wrapper.wrap(text) == expect
    text = 'Well, Doctor? What do you think?'
    expect = ['Well, Doctor?  What do you think?']
    assert wrapper.wrap(text) == expect
    text = 'Well, Doctor?\nWhat do you think?'
    assert wrapper.wrap(text) == expect
    text = 'I say, chaps! Anyone for "tennis?"\nHmmph!'
    expect = ['I say, chaps!  Anyone for "tennis?"  Hmmph!']
    assert wrapper.wrap(text) == expect
    wrapper.width = 20
    expect = ['I say, chaps!', 'Anyone for "tennis?"', 'Hmmph!']
    assert wrapper.wrap(text) == expect
    text = 'And she said, "Go to hell!"\nCan you believe that?'
    expect = ['And she said, "Go to', 'hell!"  Can you', 'believe that?']
    assert wrapper.wrap(text) == expect
    wrapper.width = 60
    expect = ['And she said, "Go to hell!"  Can you believe that?']
    assert wrapper.wrap(text) == expect
    text = 'File stdio.h is nice.'
    expect = ['File stdio.h is nice.']
    assert wrapper.wrap(text) == expect
    print('WrapTestCase.test_fix_sentence_endings')


# test_textwrap.WrapTestCase.test_wrap_short
def test_wrap_short() -> None:
    text = 'This is a\nshort paragraph.'
    assert wrap(text, 20) == ['This is a short', 'paragraph.']
    assert wrap(text, 40) == ['This is a short paragraph.']
    print('WrapTestCase.test_wrap_short')


# test_textwrap.WrapTestCase.test_wrap_short_1line
def test_wrap_short_1line() -> None:
    text = 'This is a short line.'
    assert wrap(text, 30) == ['This is a short line.']
    assert wrap(text, 30, initial_indent='(1) ') == ['(1) This is a short line.']
    print('WrapTestCase.test_wrap_short_1line')


# test_textwrap.WrapTestCase.test_hyphenated
def test_hyphenated() -> None:
    wrapper = TextWrapper(width=45)
    text = "this-is-a-useful-feature-for-reformatting-posts-from-tim-peters'ly"
    assert wrap(text, 40) == ['this-is-a-useful-feature-for-', "reformatting-posts-from-tim-peters'ly"]
    assert wrap(text, 41) == ['this-is-a-useful-feature-for-', "reformatting-posts-from-tim-peters'ly"]
    assert wrap(text, 42) == ['this-is-a-useful-feature-for-reformatting-', "posts-from-tim-peters'ly"]
    expect = "this-|is-|a-|useful-|feature-|for-|reformatting-|posts-|from-|tim-|peters'ly".split('|')
    assert wrap(text, 1, break_long_words=False) == expect
    assert wrapper._split(text) == expect
    assert wrapper._split('e-mail') == ['e-mail']
    assert wrapper._split('Jelly-O') == ['Jelly-O']
    assert wrapper._split('half-a-crown') == 'half-|a-|crown'.split('|')
    print('WrapTestCase.test_hyphenated')


# test_textwrap.WrapTestCase.test_hyphenated_numbers
def test_hyphenated_numbers() -> None:
    text = 'Python 1.0.0 was released on 1994-01-26.  Python 1.0.1 was\nreleased on 1994-02-15.'
    assert wrap(text, 30) == ['Python 1.0.0 was released on', '1994-01-26.  Python 1.0.1 was', 'released on 1994-02-15.']
    assert wrap(text, 40) == ['Python 1.0.0 was released on 1994-01-26.', 'Python 1.0.1 was released on 1994-02-15.']
    assert wrap(text, 1, break_long_words=False) == text.split()
    text = 'I do all my shopping at 7-11.'
    assert wrap(text, 25) == ['I do all my shopping at', '7-11.']
    assert wrap(text, 27) == ['I do all my shopping at', '7-11.']
    assert wrap(text, 29) == ['I do all my shopping at 7-11.']
    assert wrap(text, 1, break_long_words=False) == text.split()
    print('WrapTestCase.test_hyphenated_numbers')


# test_textwrap.WrapTestCase.test_em_dash
def test_em_dash() -> None:
    wrapper = TextWrapper(width=45)
    text = 'Em-dashes should be written -- thus.'
    assert wrap(text, 25) == ['Em-dashes should be', 'written -- thus.']
    assert wrap(text, 29) == ['Em-dashes should be written', '-- thus.']
    expect = ['Em-dashes should be written --', 'thus.']
    assert wrap(text, 30) == expect
    assert wrap(text, 35) == expect
    assert wrap(text, 36) == ['Em-dashes should be written -- thus.']
    text = 'You can also do--this or even---this.'
    expect = ['You can also do', '--this or even', '---this.']
    assert wrap(text, 15) == expect
    assert wrap(text, 16) == expect
    expect = ['You can also do--', 'this or even---', 'this.']
    assert wrap(text, 17) == expect
    assert wrap(text, 19) == expect
    expect = ['You can also do--this or even', '---this.']
    assert wrap(text, 29) == expect
    assert wrap(text, 31) == expect
    expect = ['You can also do--this or even---', 'this.']
    assert wrap(text, 32) == expect
    assert wrap(text, 35) == expect
    text = "Here's an -- em-dash and--here's another---and another!"
    expect = ["Here's", ' ', 'an', ' ', '--', ' ', 'em-', 'dash', ' ', 'and', '--', "here's", ' ', 'another', '---', 'and', ' ', 'another!']
    assert wrapper._split(text) == expect
    text = 'and then--bam!--he was gone'
    expect = ['and', ' ', 'then', '--', 'bam!', '--', 'he', ' ', 'was', ' ', 'gone']
    assert wrapper._split(text) == expect
    print('WrapTestCase.test_em_dash')


# test_textwrap.WrapTestCase.test_unix_options
def test_unix_options() -> None:
    wrapper = TextWrapper(width=45)
    text = 'You should use the -n option, or --dry-run in its long form.'
    assert wrap(text, 20) == ['You should use the', '-n option, or --dry-', 'run in its long', 'form.']
    assert wrap(text, 21) == ['You should use the -n', 'option, or --dry-run', 'in its long form.']
    expect = ['You should use the -n option, or', '--dry-run in its long form.']
    assert wrap(text, 32) == expect
    assert wrap(text, 34) == expect
    assert wrap(text, 35) == expect
    assert wrap(text, 38) == expect
    expect = ['You should use the -n option, or --dry-', 'run in its long form.']
    assert wrap(text, 39) == expect
    assert wrap(text, 41) == expect
    expect = ['You should use the -n option, or --dry-run', 'in its long form.']
    assert wrap(text, 42) == expect
    text = 'the -n option, or --dry-run or --dryrun'
    expect = ['the', ' ', '-n', ' ', 'option,', ' ', 'or', ' ', '--dry-', 'run', ' ', 'or', ' ', '--dryrun']
    assert wrapper._split(text) == expect
    print('WrapTestCase.test_unix_options')


# test_textwrap.WrapTestCase.test_funky_hyphens
def test_funky_hyphens() -> None:
    wrapper = TextWrapper(width=45)
    assert wrapper._split('what the--hey!') == ['what', ' ', 'the', '--', 'hey!']
    assert wrapper._split('what the--') == ['what', ' ', 'the--']
    assert wrapper._split('what the--.') == ['what', ' ', 'the--.']
    assert wrapper._split('--text--.') == ['--text--.']
    assert wrapper._split('--option') == ['--option']
    assert wrapper._split('--option-opt') == ['--option-', 'opt']
    assert wrapper._split('foo --option-opt bar') == ['foo', ' ', '--option-', 'opt', ' ', 'bar']
    print('WrapTestCase.test_funky_hyphens')


# test_textwrap.WrapTestCase.test_punct_hyphens
def test_punct_hyphens() -> None:
    wrapper = TextWrapper(width=45)
    assert wrapper._split("the 'wibble-wobble' widget") == ['the', ' ', "'wibble-", "wobble'", ' ', 'widget']
    assert wrapper._split('the "wibble-wobble" widget') == ['the', ' ', '"wibble-', 'wobble"', ' ', 'widget']
    assert wrapper._split('the (wibble-wobble) widget') == ['the', ' ', '(wibble-', 'wobble)', ' ', 'widget']
    assert wrapper._split("the ['wibble-wobble'] widget") == ['the', ' ', "['wibble-", "wobble']", ' ', 'widget']
    assert wrapper._split("what-d'you-call-it.") == "what-d'you-|call-|it.".split('|')
    print('WrapTestCase.test_punct_hyphens')


# test_textwrap.WrapTestCase.test_funky_parens
def test_funky_parens() -> None:
    wrapper = TextWrapper(width=45)
    assert wrapper._split('foo (--option) bar') == ['foo', ' ', '(--option)', ' ', 'bar']
    assert wrapper._split('foo (bar) baz') == ['foo', ' ', '(bar)', ' ', 'baz']
    assert wrapper._split('blah (ding dong), wubba') == ['blah', ' ', '(ding', ' ', 'dong),', ' ', 'wubba']
    print('WrapTestCase.test_funky_parens')


# test_textwrap.WrapTestCase.test_drop_whitespace_false
def test_drop_whitespace_false() -> None:
    text = ' This is a    sentence with     much whitespace.'
    assert wrap(text, 10, drop_whitespace=False) == [' This is a', '    ', 'sentence ', 'with     ', 'much white', 'space.']
    print('WrapTestCase.test_drop_whitespace_false')


# test_textwrap.WrapTestCase.test_drop_whitespace_false_whitespace_only
def test_drop_whitespace_false_whitespace_only() -> None:
    assert wrap('   ', 6, drop_whitespace=False) == ['   ']
    print('WrapTestCase.test_drop_whitespace_false_whitespace_only')


# test_textwrap.WrapTestCase.test_drop_whitespace_false_whitespace_only_with_indent
def test_drop_whitespace_false_whitespace_only_with_indent() -> None:
    assert wrap('   ', 6, drop_whitespace=False, initial_indent='  ') == ['     ']
    print('WrapTestCase.test_drop_whitespace_false_whitespace_only_with_indent')


# test_textwrap.WrapTestCase.test_drop_whitespace_whitespace_only
def test_drop_whitespace_whitespace_only() -> None:
    assert wrap('  ', 6) == []
    print('WrapTestCase.test_drop_whitespace_whitespace_only')


# test_textwrap.WrapTestCase.test_drop_whitespace_leading_whitespace
def test_drop_whitespace_leading_whitespace() -> None:
    text = ' This is a sentence with leading whitespace.'
    assert wrap(text, 50) == [' This is a sentence with leading whitespace.']
    assert wrap(text, 30) == [' This is a sentence with', 'leading whitespace.']
    print('WrapTestCase.test_drop_whitespace_leading_whitespace')


# test_textwrap.WrapTestCase.test_drop_whitespace_whitespace_line
def test_drop_whitespace_whitespace_line() -> None:
    text = 'abcd    efgh'
    assert wrap(text, 6, drop_whitespace=False) == ['abcd', '    ', 'efgh']
    assert wrap(text, 6) == ['abcd', 'efgh']
    print('WrapTestCase.test_drop_whitespace_whitespace_line')


# test_textwrap.WrapTestCase.test_drop_whitespace_whitespace_only_with_indent
def test_drop_whitespace_whitespace_only_with_indent() -> None:
    assert wrap('  ', 6, initial_indent='++') == []
    print('WrapTestCase.test_drop_whitespace_whitespace_only_with_indent')


# test_textwrap.WrapTestCase.test_drop_whitespace_whitespace_indent
def test_drop_whitespace_whitespace_indent() -> None:
    assert wrap('abcd efgh', 6, initial_indent='  ', subsequent_indent='  ') == ['  abcd', '  efgh']
    print('WrapTestCase.test_drop_whitespace_whitespace_indent')


# test_textwrap.WrapTestCase.test_split
def test_split() -> None:
    wrapper = TextWrapper(width=45)
    text = 'Hello there -- you goof-ball, use the -b option!'
    result = wrapper._split(text)
    assert result == ['Hello', ' ', 'there', ' ', '--', ' ', 'you', ' ', 'goof-', 'ball,', ' ', 'use', ' ', 'the', ' ', '-b', ' ', 'option!']
    print('WrapTestCase.test_split')


# test_textwrap.WrapTestCase.test_break_on_hyphens
def test_break_on_hyphens() -> None:
    text = 'yaba daba-doo'
    assert wrap(text, 10, break_on_hyphens=True) == ['yaba daba-', 'doo']
    assert wrap(text, 10, break_on_hyphens=False) == ['yaba', 'daba-doo']
    print('WrapTestCase.test_break_on_hyphens')


# test_textwrap.WrapTestCase.test_bad_width
def test_bad_width() -> None:
    text = "Whatever, it doesn't matter."
    raised = False
    try:
        wrap(text, 0)
    except ValueError:
        raised = True
    assert raised
    raised = False
    try:
        wrap(text, -1)
    except ValueError:
        raised = True
    assert raised
    print('WrapTestCase.test_bad_width')


# test_textwrap.WrapTestCase.test_no_split_at_umlaut
def test_no_split_at_umlaut() -> None:
    text = 'Die Empfänger-Auswahl'
    assert wrap(text, 13) == ['Die', 'Empfänger-', 'Auswahl']
    print('WrapTestCase.test_no_split_at_umlaut')


# test_textwrap.WrapTestCase.test_non_breaking_space
def test_non_breaking_space() -> None:
    text = 'This is a sentence with non-breaking\xa0space.'
    assert wrap(text, 20, break_on_hyphens=True) == ['This is a sentence', 'with non-', 'breaking\xa0space.']
    assert wrap(text, 20, break_on_hyphens=False) == ['This is a sentence', 'with', 'non-breaking\xa0space.']
    print('WrapTestCase.test_non_breaking_space')


test_simple()
test_empty_string()
test_empty_string_with_initial_indent()
test_whitespace()
test_fix_sentence_endings()
test_wrap_short()
test_wrap_short_1line()
test_hyphenated()
test_hyphenated_numbers()
test_em_dash()
test_unix_options()
test_funky_hyphens()
test_punct_hyphens()
test_funky_parens()
test_drop_whitespace_false()
test_drop_whitespace_false_whitespace_only()
test_drop_whitespace_false_whitespace_only_with_indent()
test_drop_whitespace_whitespace_only()
test_drop_whitespace_leading_whitespace()
test_drop_whitespace_whitespace_line()
test_drop_whitespace_whitespace_only_with_indent()
test_drop_whitespace_whitespace_indent()
test_split()
test_break_on_hyphens()
test_bad_width()
test_no_split_at_umlaut()
test_non_breaking_space()
