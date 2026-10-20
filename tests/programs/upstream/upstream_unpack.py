# Adapted from CPython 3.13.16 Lib/test/test_unpack.py and Lib/test/test_unpack_ex.py, their
# doctests (`doctests`), commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each doctest section becomes a function: unpack_* are test_unpack.py's (unpack tuple, list,
# implied tuple, string, single element, a list of wrong size, sequence too short, empty
# iterables, unpacking to an empty iterable), ex_* test_unpack_ex.py's (unpack tuple, list,
# implied tuple, nested implied tuple, string, long and short sequences, generic sequence,
# in a for statement, in a list, multiple targets, assignment unpacking, dict display element
# unpacking, list display element unpacking, iterable argument unpacking, sequences too short).
# A doctest's `>>> expr` that shows True prints it; a traceback is a try statement that prints
# the exception. Seq() (a sequence class iterated through __getitem__) is the list of its items,
# [0, 1, 2]; `range(5)` as a value is list(range(5)); the for loop's rows of different lengths are
# lists; an empty dict display that nothing types is annotated; a name that a later section binds
# to another type is local to its function, and an exception variable has a name of its own.
# EXCLUDED upstream cases:
# - Seq() and BadSeq() themselves (rejected: "iterating over Seq by its __getitem__ is not
#   supported (CPython calls __getitem__(0), __getitem__(1), ... until IndexError): define
#   __iter__"), and so BozoError's two cases
# - `a, b, c = 7`, `() = 42` (compile-time "cannot unpack int into 3 targets" / "... into 0
#   targets") and `a, *b = 7` (compile-time "cannot unpack non-iterable int object", CPython's
#   message: tests/errors/upstream/upstream_unpack_ex_non_iterable.py): a type error that CPython raises
#   when the code runs is a compile-time error here
#   (documented); `a, b = t` of a 3-tuple likewise ("cannot unpack tuple[int,int,int] into 2
#   targets")
# - test_unpack_ex's `for a, *b, c in [(1,2,3), (4,5,6,7)]` with tuples (rejected: "expected
#   tuple[int,int,int], got tuple[int,int,int,int]"; its lists are adopted)
# - `*a, b, c = a, b, *c` where `a` is the int of the line before (rejected: "expected int, got
#   list[int]"; a variable keeps one type here, so the adapted line names new variables)
# - set display element unpacking `{1, *a, 0, 4}` (rejected: "unpacking in a set display
#   ({*xs}) is not supported", #515) and `{1, *1, 0, 4}`
# - `{**1}`, `{**[]}` (compile-time type errors), the eval() of 1000 `**` displays,
#   `f(**original_dict, y=2)` (rejected: "** of a dict[str,int] is not supported: of a
#   function's **kwargs, or a dict display with str keys, it is", #516), CrazyDict
#   (collections.abc.MutableMapping subclass, generator __iter__), the overridden-parameter
#   TypeErrors of f(x=5, **{'x': 3}, ...) and of f(**{1: 3}, **{1: 5})
# - the SyntaxError doctests (multiple starred expressions, starred assignment target outside a
#   list or tuple, starred expressions in comprehensions, `dict(**x for x in ...)`): Pystachy
#   reports each with CPython's message at compile time (checked with tools/syntax_sweep.py);
#   compile() of the 256-target star unpacking; TestCornerCases (exec())
def unpack_tuple() -> None:
    t = (1, 2, 3)
    a, b, c = t
    print(a == 1 and b == 2 and c == 3)


def unpack_list() -> None:
    l = [4, 5, 6]
    a, b, c = l
    print(a == 4 and b == 5 and c == 6)


def unpack_implied_tuple() -> None:
    a, b, c = 7, 8, 9
    print(a == 7 and b == 8 and c == 9)


def unpack_string() -> None:
    a, b, c = 'one'
    print(a == 'o' and b == 'n' and c == 'e')


def unpack_single_element() -> None:
    st = (99,)
    sl = [100]
    a, = st
    print(a)
    b, = sl
    print(b)


def unpack_tuple_wrong_size() -> None:
    l = [4, 5, 6]
    try:
        a, b = l
    except ValueError as e:
        print(e)


def unpack_sequence_too_short() -> None:
    try:
        a, b, c, d = [0, 1, 2]
    except ValueError as e:
        print(e)


def unpack_empty_iterables() -> None:
    () = []
    [] = ()
    [] = []
    () = ()
    print("ok")


def unpack_to_empty_iterable() -> None:
    try:
        () = [42]
    except ValueError as e:
        print(e)


def ex_unpack_tuple() -> None:
    t = (1, 2, 3)
    a, *b, c = t
    print(a == 1 and b == [2] and c == 3)


def ex_unpack_list() -> None:
    l = [4, 5, 6]
    a, *b = l
    print(a == 4 and b == [5, 6])


def ex_unpack_implied_tuple() -> None:
    *a, = 7, 8, 9
    print(a == [7, 8, 9])


def ex_unpack_nested_implied_tuple() -> None:
    [*[*a]] = [[7,8,9]]
    print(a == [[7,8,9]])


def ex_unpack_string() -> None:
    a, *b = 'one'
    print(a == 'o' and b == ['n', 'e'])


def ex_unpack_long_sequence() -> None:
    a, b, c, *d, e, f, g = range(10)
    print((a, b, c, d, e, f, g) == (0, 1, 2, [3, 4, 5, 6], 7, 8, 9))


def ex_unpack_short_sequence() -> None:
    a, *b, c = (1, 2)
    print(a == 1 and c == 2 and b == [])


def ex_unpack_generic_sequence() -> None:
    a, *b = [0, 1, 2]
    print(a == 0 and b == [1, 2])


def ex_unpack_in_for() -> None:
    for a, *b, c in [[1,2,3], [4,5,6,7]]:
        print(a, b, c)


def ex_unpack_in_list() -> None:
    [a, *b, c] = range(5)
    print(a == 0 and b == [1, 2, 3] and c == 4)


def ex_multiple_targets() -> None:
    a, *b, c = *d, e = list(range(5))
    print(a == 0 and b == [1, 2, 3] and c == 4 and d == [0, 1, 2, 3] and e == 4)


def ex_assignment_unpacking() -> None:
    a, b, *c = range(5)
    print((a, b, c))
    *a2, b2, c2 = a, b, *c
    print((a2, b2, c2))


def ex_dict_display_unpacking() -> None:
    kwds = {'z': 0, 'w': 12}
    print(sorted({'x': 1, 'y': 2, **kwds}.items()))
    print(sorted({**{'x': 1}, 'y': 2, **{'z': 3}}.items()))
    print(sorted({**{'x': 1}, 'y': 2, **{'x': 3}}.items()))
    print(sorted({**{'x': 1}, **{'x': 3}, 'x': 4}.items()))


def ex_dict_display_empty() -> None:
    e: dict[int, int] = {}
    print({**e})
    a: dict[int, int] = {}
    {**a}[0] = 1
    print(a)


def ex_dict_display_int_keys() -> None:
    print({0:1, **{0:2}, 0:3, 0:4})


def ex_list_display_unpacking() -> None:
    a, b, c = [0, 1, 2], 3, 4
    print([*a, b, c])


def ex_iterable_argument_unpacking() -> None:
    print(*[1], *[2], 3)


def ex_sequence_too_short() -> None:
    try:
        a, *b, c, d, e = [0, 1, 2]
    except ValueError as ex:
        print(ex)


def ex_sequence_too_short_target_last() -> None:
    try:
        a, b, c, d, *e = [0, 1, 2]
    except ValueError as ex:
        print(ex)


unpack_tuple()
unpack_list()
unpack_implied_tuple()
unpack_string()
unpack_single_element()
unpack_tuple_wrong_size()
unpack_sequence_too_short()
unpack_empty_iterables()
unpack_to_empty_iterable()
ex_unpack_tuple()
ex_unpack_list()
ex_unpack_implied_tuple()
ex_unpack_nested_implied_tuple()
ex_unpack_string()
ex_unpack_long_sequence()
ex_unpack_short_sequence()
ex_unpack_generic_sequence()
ex_unpack_in_for()
ex_unpack_in_list()
ex_multiple_targets()
ex_assignment_unpacking()
ex_dict_display_unpacking()
ex_dict_display_empty()
ex_dict_display_int_keys()
ex_list_display_unpacking()
ex_iterable_argument_unpacking()
ex_sequence_too_short()
ex_sequence_too_short_target_last()
