# Adapted from CPython 3.13.16 Lib/test/test_pprint.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91. Source SHA-256:
# e189a2517eb6569907fdfd8dcb5f820e96ce3cf97275aa288623b6441af91e19.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# unittest scaffolding becomes annotated functions and plain assertions. CPython's own pprint
# records the oracle, while JIT/AOT execute lib/pprint.py.
# Complete methods, with every input and assertion: test_sort_dict (its dict annotated),
# test_nested_indentations (its list annotated, its dict a display), test_compact and
# test_compact_width (its nested list written out). test_str_wrap keeps every literal
# assertion (its dict of an int and two str values annotated), and test_bytes_wrap all but the
# two of a dict holding ints beside bytes (no union holds bytes); their closing loops print
# each width's result, where upstream evaluates it with eval().
# Partial methods keep the assertions named here and leave out inputs that have no static type
# or no support: test_init (not the sixth positional argument, a compile-time error),
# test_basic and test_same_as_repr (no complex, bytearray, Ellipsis, range, module, method or
# subclass values, nor lists holding ints and a list), test_unreadable (an object(); no class,
# module or function as a value), test_basic_line_wrap and test_set_reprs (no dict, list, tuple,
# set or frozenset subclasses), test_integer (no int subclass), test_sorted_dict (not the dict
# whose keys are an int, a str and a tuple), test_depth (not the list holding ints and lists).
# Not claimed: test_stdout_is_None, test_knotted, test_container_repr_override_called,
# test_width, test_set_of_sets_reprs, test_subclassing, the sorting of unorderable values, and
# the methods for collections, types, dataclasses and bytearray.
import io
import pprint


# test_pprint.QueryTestCase.test_init
def test_init() -> None:
    pp = pprint.PrettyPrinter()
    pp2 = pprint.PrettyPrinter(indent=4, width=40, depth=5,
                               stream=io.StringIO(), compact=True)
    pp3 = pprint.PrettyPrinter(4, 40, 5, io.StringIO())
    pp4 = pprint.PrettyPrinter(sort_dicts=False)
    for which in range(4):
        try:
            if which == 0:
                pprint.PrettyPrinter(indent=-1)
            elif which == 1:
                pprint.PrettyPrinter(depth=0)
            elif which == 2:
                pprint.PrettyPrinter(depth=-1)
            else:
                pprint.PrettyPrinter(width=0)
            raise AssertionError("ValueError not raised")
        except ValueError as e:
            print(e)
    print('QueryTestCase.test_init')


def check_safe(safe) -> None:
    pp = pprint.PrettyPrinter()
    # module-level convenience functions
    assert not pprint.isrecursive(safe), "expected not isrecursive for %r" % (safe,)
    assert pprint.isreadable(safe), "expected isreadable for %r" % (safe,)
    # PrettyPrinter methods
    assert not pp.isrecursive(safe), "expected not isrecursive for %r" % (safe,)
    assert pp.isreadable(safe), "expected isreadable for %r" % (safe,)


# test_pprint.QueryTestCase.test_basic
def test_basic() -> None:
    # Verify .isrecursive() and .isreadable() w/o recursion
    check_safe(2)
    check_safe(2.0)
    check_safe("abc")
    check_safe([3])
    check_safe((2, 2))
    check_safe({3: 3})
    check_safe(b"def")
    check_safe(True)
    check_safe(False)
    check_safe(None)
    check_safe(list(range(200)))
    print('QueryTestCase.test_basic')


def check_unreadable(unreadable) -> None:
    pp = pprint.PrettyPrinter()
    # module-level convenience functions
    assert not pprint.isrecursive(unreadable)
    assert not pprint.isreadable(unreadable)
    # PrettyPrinter methods
    assert not pp.isrecursive(unreadable)
    assert not pp.isreadable(unreadable)


# test_pprint.QueryTestCase.test_unreadable
def test_unreadable() -> None:
    # Not recursive but not readable anyway
    check_unreadable(object())
    print('QueryTestCase.test_unreadable')


def check_same_as_repr(simple) -> None:
    native = repr(simple)
    assert pprint.pformat(simple) == native, native
    assert pprint.pformat(simple, width=1, indent=0).replace('\n', ' ') == native, native
    assert pprint.pformat(simple, underscore_numbers=True) == native, native
    assert pprint.saferepr(simple) == native, native


# test_pprint.QueryTestCase.test_same_as_repr
def test_same_as_repr() -> None:
    empty_tuple: tuple[int, ...] = ()
    empty_list: list[int] = []
    empty_set: set[int] = set()
    empty_frozenset: frozenset[int] = frozenset()
    empty_dict: dict[int, int] = {}
    check_same_as_repr(0)
    check_same_as_repr(0.0)
    check_same_as_repr("")
    check_same_as_repr(b"")
    check_same_as_repr(empty_tuple)
    check_same_as_repr(empty_list)
    check_same_as_repr(empty_set)
    check_same_as_repr(empty_frozenset)
    check_same_as_repr(empty_dict)
    check_same_as_repr(-6)
    check_same_as_repr(-1.5)
    check_same_as_repr("x")
    check_same_as_repr(b"x")
    check_same_as_repr((3,))
    check_same_as_repr([3])
    check_same_as_repr({3: 6})
    check_same_as_repr((1, 2))
    check_same_as_repr([3, 4])
    check_same_as_repr({5: 6})
    check_same_as_repr({7})
    check_same_as_repr(frozenset({8}))
    check_same_as_repr(True)
    check_same_as_repr(False)
    check_same_as_repr(None)
    print('QueryTestCase.test_same_as_repr')


# test_pprint.QueryTestCase.test_basic_line_wrap
def test_basic_line_wrap() -> None:
    # verify basic line-wrapping operation
    o = {'RPM_cal': 0,
         'RPM_cal2': 48059,
         'Speed_cal': 0,
         'controldesk_runtime_us': 0,
         'main_code_runtime_us': 0,
         'read_io_runtime_us': 0,
         'write_io_runtime_us': 43690}
    exp = """\
{'RPM_cal': 0,
 'RPM_cal2': 48059,
 'Speed_cal': 0,
 'controldesk_runtime_us': 0,
 'main_code_runtime_us': 0,
 'read_io_runtime_us': 0,
 'write_io_runtime_us': 43690}"""
    assert pprint.pformat(o) == exp

    r = range(100)
    exp = '[%s]' % ',\n '.join(map(str, r))
    assert pprint.pformat(list(r)) == exp

    t = tuple(range(100))
    exp = '(%s)' % ',\n '.join(map(str, t))
    assert pprint.pformat(t) == exp

    # indent parameter
    r = range(100)
    exp = '[   %s]' % ',\n    '.join(map(str, r))
    assert pprint.pformat(list(r), indent=4) == exp
    print('QueryTestCase.test_basic_line_wrap')


# test_pprint.QueryTestCase.test_nested_indentations
def test_nested_indentations() -> None:
    o1 = list(range(10))
    o2 = {'first': 1, 'second': 2, 'third': 3}
    o: list[list[int] | dict[str, int]] = [o1, o2]
    expected = """\
[   [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    {'first': 1, 'second': 2, 'third': 3}]"""
    assert pprint.pformat(o, indent=4, width=42) == expected
    expected = """\
[   [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    {   'first': 1,
        'second': 2,
        'third': 3}]"""
    assert pprint.pformat(o, indent=4, width=41) == expected
    print('QueryTestCase.test_nested_indentations')


# test_pprint.QueryTestCase.test_integer
def test_integer() -> None:
    assert pprint.pformat(1234567) == '1234567'
    assert pprint.pformat(1234567, underscore_numbers=True) == '1_234_567'
    print('QueryTestCase.test_integer')


# test_pprint.QueryTestCase.test_sorted_dict
def test_sorted_dict() -> None:
    # Starting in Python 2.5, pprint sorts dict displays by key regardless
    # of how small the dictionary may be.
    # Before the change, on 32-bit Windows pformat() gave order
    # 'a', 'c', 'b' here, so this test failed.
    d = {'a': 1, 'b': 1, 'c': 1}
    assert pprint.pformat(d) == "{'a': 1, 'b': 1, 'c': 1}"
    assert pprint.pformat([d, d]) == "[{'a': 1, 'b': 1, 'c': 1}, {'a': 1, 'b': 1, 'c': 1}]"
    print('QueryTestCase.test_sorted_dict')


# test_pprint.QueryTestCase.test_sort_dict
def test_sort_dict() -> None:
    d: dict[str, int | None] = dict.fromkeys('cba')
    assert pprint.pformat(d, sort_dicts=False) == "{'c': None, 'b': None, 'a': None}"
    assert pprint.pformat([d, d], sort_dicts=False) == \
        "[{'c': None, 'b': None, 'a': None}, {'c': None, 'b': None, 'a': None}]"
    print('QueryTestCase.test_sort_dict')


# test_pprint.QueryTestCase.test_set_reprs
def test_set_reprs() -> None:
    empty_set: set[int] = set()
    assert pprint.pformat(empty_set) == 'set()'
    assert pprint.pformat(set(range(3))) == '{0, 1, 2}'
    assert pprint.pformat(set(range(7)), width=20) == '''\
{0,
 1,
 2,
 3,
 4,
 5,
 6}'''

    empty_frozenset: frozenset[int] = frozenset()
    assert pprint.pformat(empty_frozenset) == 'frozenset()'
    assert pprint.pformat(frozenset(range(3))) == 'frozenset({0, 1, 2})'
    assert pprint.pformat(frozenset(range(7)), width=20) == '''\
frozenset({0,
           1,
           2,
           3,
           4,
           5,
           6})'''
    print('QueryTestCase.test_set_reprs')


# test_pprint.QueryTestCase.test_depth
def test_depth() -> None:
    nested_tuple = (1, (2, (3, (4, (5, 6)))))
    nested_dict = {1: {2: {3: {4: {5: {6: 6}}}}}}
    assert pprint.pformat(nested_tuple) == repr(nested_tuple)
    assert pprint.pformat(nested_dict) == repr(nested_dict)

    lv1_tuple = '(1, (...))'
    lv1_dict = '{1: {...}}'
    assert pprint.pformat(nested_tuple, depth=1) == lv1_tuple
    assert pprint.pformat(nested_dict, depth=1) == lv1_dict
    print('QueryTestCase.test_depth')


# test_pprint.QueryTestCase.test_str_wrap
def test_str_wrap() -> None:
    # pprint tries to wrap strings intelligently
    fox = 'the quick brown fox jumped over a lazy dog'
    assert pprint.pformat(fox, width=19) == """\
('the quick brown '
 'fox jumped over '
 'a lazy dog')"""
    mixed: dict[str, int | str] = {'a': 1, 'b': fox, 'c': 2}
    assert pprint.pformat(mixed,
                          width=25) == """\
{'a': 1,
 'b': 'the quick brown '
      'fox jumped over '
      'a lazy dog',
 'c': 2}"""
    # With some special characters
    # - \n always triggers a new line in the pprint
    # - \t and \n are escaped
    # - non-ASCII is allowed
    # - an apostrophe doesn't disrupt the pprint
    special = "Portons dix bons \"whiskys\"\nà l'avocat goujat\t qui fumait au zoo"
    assert pprint.pformat(special, width=68) == repr(special)
    assert pprint.pformat(special, width=31) == """\
('Portons dix bons "whiskys"\\n'
 "à l'avocat goujat\\t qui "
 'fumait au zoo')"""
    assert pprint.pformat(special, width=20) == """\
('Portons dix bons '
 '"whiskys"\\n'
 "à l'avocat "
 'goujat\\t qui '
 'fumait au zoo')"""
    assert pprint.pformat([[[[[special]]]]], width=35) == """\
[[[[['Portons dix bons "whiskys"\\n'
     "à l'avocat goujat\\t qui "
     'fumait au zoo']]]]]"""
    assert pprint.pformat([[[[[special]]]]], width=25) == """\
[[[[['Portons dix bons '
     '"whiskys"\\n'
     "à l'avocat "
     'goujat\\t qui '
     'fumait au zoo']]]]]"""
    assert pprint.pformat([[[[[special]]]]], width=23) == """\
[[[[['Portons dix '
     'bons "whiskys"\\n'
     "à l'avocat "
     'goujat\\t qui '
     'fumait au '
     'zoo']]]]]"""
    # An unwrappable string is formatted as its repr
    unwrappable = "x" * 100
    assert pprint.pformat(unwrappable, width=80) == repr(unwrappable)
    assert pprint.pformat('') == "''"
    # Check that the pprint is a usable repr
    special *= 10
    for width in range(3, 40):
        formatted = pprint.pformat(special, width=width)
        print(formatted)
        formatted = pprint.pformat([special] * 2, width=width)
        print(formatted)
    print('QueryTestCase.test_str_wrap')


# test_pprint.QueryTestCase.test_compact
def test_compact() -> None:
    o = ([list(range(i * i)) for i in range(5)] +
         [list(range(i)) for i in range(6)])
    expected = """\
[[], [0], [0, 1, 2, 3],
 [0, 1, 2, 3, 4, 5, 6, 7, 8],
 [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13,
  14, 15],
 [], [0], [0, 1], [0, 1, 2], [0, 1, 2, 3],
 [0, 1, 2, 3, 4]]"""
    assert pprint.pformat(o, width=47, compact=True) == expected
    print('QueryTestCase.test_compact')


# test_pprint.QueryTestCase.test_compact_width
def test_compact_width() -> None:
    levels = 20
    number = 10
    # (upstream wraps o in a list levels - 1 times in a loop; each list has a type of its own)
    o = [[[[[[[[[[[[[[[[[[[[0] * number]]]]]]]]]]]]]]]]]]]
    for w in range(levels * 2 + 1, levels + 3 * number - 1):
        lines = pprint.pformat(o, width=w, compact=True).splitlines()
        maxwidth = max(map(len, lines))
        assert maxwidth <= w
        assert maxwidth > w - 3
    print('QueryTestCase.test_compact_width')


# test_pprint.QueryTestCase.test_bytes_wrap
def test_bytes_wrap() -> None:
    assert pprint.pformat(b'', width=1) == "b''"
    assert pprint.pformat(b'abcd', width=1) == "b'abcd'"
    letters = b'abcdefghijklmnopqrstuvwxyz'
    assert pprint.pformat(letters, width=29) == repr(letters)
    assert pprint.pformat(letters, width=19) == """\
(b'abcdefghijkl'
 b'mnopqrstuvwxyz')"""
    assert pprint.pformat(letters, width=18) == """\
(b'abcdefghijkl'
 b'mnopqrstuvwx'
 b'yz')"""
    assert pprint.pformat(letters, width=16) == """\
(b'abcdefghijkl'
 b'mnopqrstuvwx'
 b'yz')"""
    special = bytes(range(16))
    assert pprint.pformat(special, width=61) == repr(special)
    assert pprint.pformat(special, width=48) == """\
(b'\\x00\\x01\\x02\\x03\\x04\\x05\\x06\\x07\\x08\\t\\n\\x0b'
 b'\\x0c\\r\\x0e\\x0f')"""
    assert pprint.pformat(special, width=32) == """\
(b'\\x00\\x01\\x02\\x03'
 b'\\x04\\x05\\x06\\x07\\x08\\t\\n\\x0b'
 b'\\x0c\\r\\x0e\\x0f')"""
    assert pprint.pformat(special, width=1) == """\
(b'\\x00\\x01\\x02\\x03'
 b'\\x04\\x05\\x06\\x07'
 b'\\x08\\t\\n\\x0b'
 b'\\x0c\\r\\x0e\\x0f')"""
    assert pprint.pformat([[[[[[letters]]]]]], width=25) == """\
[[[[[[b'abcdefghijklmnop'
      b'qrstuvwxyz']]]]]]"""
    assert pprint.pformat([[[[[[special]]]]]], width=41) == """\
[[[[[[b'\\x00\\x01\\x02\\x03\\x04\\x05\\x06\\x07'
      b'\\x08\\t\\n\\x0b\\x0c\\r\\x0e\\x0f']]]]]]"""
    # Check that the pprint is a usable repr
    for width in range(1, 64):
        formatted = pprint.pformat(special, width=width)
        print(formatted)
        formatted = pprint.pformat([special] * 2, width=width)
        print(formatted)
    print('QueryTestCase.test_bytes_wrap')


test_init()
test_basic()
test_unreadable()
test_same_as_repr()
test_basic_line_wrap()
test_nested_indentations()
test_integer()
test_sorted_dict()
test_sort_dict()
test_set_reprs()
test_depth()
test_str_wrap()
test_compact()
test_compact_width()
test_bytes_wrap()
