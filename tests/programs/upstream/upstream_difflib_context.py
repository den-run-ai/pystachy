# Selected context-diff checks from CPython 3.13.16 Lib/test/test_difflib.py,
# commit cbc944f4bc59639a444dd971c737788ba2283a91, original SHA-256:
# dc6b140c8dd31e6971888070ea5175a0ab72ecadbdc96956071ceb062f34e636.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# TestOutputFormat.test_tab_delimiter and test_no_trailing_tab_on_empty_filedate
# retain only their context_diff checks (unified_diff is covered separately).
# test_range_format_context retains all five assertions. unittest assertions
# become plain assertions and the positional argument list is expanded explicitly.
# Additional public-API cases cover every opcode, empty and identical inputs,
# context grouping, Unicode and missing final newlines; recordings come from CPython.
# Excludes diff_bytes, invalid statically typed arguments and the rest of difflib.
import difflib


def test_tab_delimiter() -> None:
    delta = difflib.context_diff('one', 'two', 'Original', 'Current',
                                '2005-01-26 23:30:50', '2010-04-02 10:20:52',
                                lineterm='')
    assert list(delta)[:2] == ['*** Original\t2005-01-26 23:30:50',
                              '--- Current\t2010-04-02 10:20:52']


def test_no_trailing_tab_on_empty_filedate() -> None:
    delta = difflib.context_diff('one', 'two', 'Original', 'Current', lineterm='')
    assert list(delta)[:2] == ['*** Original', '--- Current']


def test_range_format_context() -> None:
    assert difflib._format_range_context(3, 3) == '3'
    assert difflib._format_range_context(3, 4) == '4'
    assert difflib._format_range_context(3, 5) == '4,5'
    assert difflib._format_range_context(3, 6) == '4,6'
    assert difflib._format_range_context(0, 0) == '0'


test_tab_delimiter()
test_no_trailing_tab_on_empty_filedate()
test_range_format_context()
print('context_diff: 3 selected TestOutputFormat methods passed')

empty: list[str] = []
print('empty', list(difflib.context_diff(empty, empty)))
print('identical', list(difflib.context_diff(['a\n'], ['a\n'])))
print('insert', list(difflib.context_diff(empty, ['new\n'], n=0)))
print('delete', list(difflib.context_diff(['old\n'], empty, n=0)))
print('replace', list(difflib.context_diff(['old\n'], ['new\n'], n=0)))
print('equal-context', list(difflib.context_diff(['a\n', 'old\n', 'z\n'],
                                               ['a\n', 'new\n', 'z\n'])))
before = ['A\n', 'b\n', 'c\n', 'd\n', 'e\n', 'f\n', 'G\n']
after = ['a\n', 'b\n', 'c\n', 'd\n', 'e\n', 'f\n', 'g\n']
print('split-groups', list(difflib.context_diff(before, after, n=1)))
print('joined-groups', list(difflib.context_diff(before, after, n=3)))
print('no-newlines', list(difflib.context_diff(['same', 'old'], ['same', 'new'],
                                             fromfile='old.txt', tofile='new.txt',
                                             lineterm='')))
print('unicode', list(difflib.context_diff(['café\n', '猫\n'], ['cafe\n', '猫\n'],
                                        fromfile='旧', tofile='新',
                                        fromfiledate='1 fév', tofiledate='2 fév')))
print('mixed-changes', list(difflib.context_diff(['one\n', 'two\n', 'three\n', 'four\n'],
                                              ['zero\n', 'one\n', 'tree\n', 'four\n'])))
