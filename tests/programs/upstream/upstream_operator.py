# Adapted from CPython 3.13.16 Lib/test/test_operator.py, class OperatorTestCase (run with
# operator = Lib/operator.py, as lib/operator.py adapts it): test_lt, test_le, test_eq, test_ne,
# test_ge and test_gt (test_comparisons; test_eq's and test_ne's C in test_eq_ne_raises),
# test_abs, test_add, test_bitwise_and, test_floordiv, test_truediv, test_invert, test_lshift,
# test_mod, test_mul, test_neg, test_bitwise_or, test_pos, test_pow, test_rshift, test_sub and
# test_bitwise_xor (test_arithmetic), test_matmul, test_concat, test_delitem, test_getitem,
# test_indexOf, test_contains, test_setitem, test_truth, test_is and test_is_not (test_is),
# test_not_, test_attrgetter, test_itemgetter and test_methodcaller; commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# assertEqual(a, b), assertTrue(x), assertFalse(x) and assertIsNone(x) print and assert;
# assertRaises(E, f, *args) is a try statement that prints the exception. The classes of the
# methods are module classes (renamed A_2, ... where names repeat), with annotated special
# methods; Seq1's __add__ takes a Seq1. A range as a value is list(range(...)). An empty list
# that nothing types is annotated. test_attrgetter's A gets its fields in __init__ (an object
# has the fields its class gives it), its multiple gets are on a class R of their own and its
# recursive gets (child.name) on A_2, whose child is an A_2 | None; test_itemgetter's getters of
# other indices or keys have names of their own (each itemgetter is a type of its own here);
# dict(key='val') is {'key': 'val'}; test_methodcaller's A_3 and A_4 hold its methods.
# EXCLUDED upstream cases:
# - the TypeErrors of calls that do not fit (operator.lt(), operator.add(None, None),
#   attrgetter(2), ...): compile-time errors here; the complex number cases (1j, 2j)
# - operator.index() of an int or a bool (rejected inside lib/operator.py: "'int' has no method
#   '__index__'", #510): test_index; operator.length_hint() (rejected inside lib/operator.py:
#   "unsupported call type(list[int])"); operator.iadd() & co (test_inplace: an in-place operator
#   that returns another type rebinds its operand to it, rejected inside lib/operator.py:
#   "expected IC, got str"), operator.iconcat() ("type(x).__name__ is only supported for
#   exceptions"), test_iconcat_without_getitem; operator.call() of a function with **kwargs
#   whose result is compared with dicts (rejected: "cannot infer the type of an empty dict" /
#   "cannot compare kw[...] == dict[...]"): test_call
# - countOf() and indexOf() of [nan, nan, 21] (NaN identity: documented, floats are unboxed) and
#   of [{}, 1, {}, 2] (a list of dicts and ints); BadIterable (an __iter__ that only raises);
#   test_indexOf's `it` part is kept
# - attrgetter('rank') of an object without it (rejected at compile time inside
#   lib/operator.py: "'A' object has no attribute 'rank'"), its SyntaxError-raising __getattr__,
#   attrgetter('child.', ...) & co; itemgetter(slice(2, 4)) (#501), itemgetter(0) of
#   range(100, 200) and of a tuple subclass, the SyntaxError-raising __getitem__;
#   methodcaller('foo') with no arguments (an IndexError at run time in CPython, a compile-time
#   "tuple index out of range" here); test_attrgetter_signature & co, test_dunder_is_original,
#   test___all__, pickling, and the C-operator variants
import operator


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def test_comparisons() -> None:
    check("lt", operator.lt(1, 0), False)
    check("lt", operator.lt(1, 0.0), False)
    check("lt", operator.lt(1, 1), False)
    check("lt", operator.lt(1, 1.0), False)
    check("lt", operator.lt(1, 2), True)
    check("lt", operator.lt(1, 2.0), True)
    check("le", operator.le(1, 0), False)
    check("le", operator.le(1, 0.0), False)
    check("le", operator.le(1, 1), True)
    check("le", operator.le(1, 1.0), True)
    check("le", operator.le(1, 2), True)
    check("le", operator.le(1, 2.0), True)
    check("eq", operator.eq(1, 0), False)
    check("eq", operator.eq(1, 0.0), False)
    check("eq", operator.eq(1, 1), True)
    check("eq", operator.eq(1, 1.0), True)
    check("eq", operator.eq(1, 2), False)
    check("eq", operator.eq(1, 2.0), False)
    check("ne", operator.ne(1, 0), True)
    check("ne", operator.ne(1, 0.0), True)
    check("ne", operator.ne(1, 1), False)
    check("ne", operator.ne(1, 1.0), False)
    check("ne", operator.ne(1, 2), True)
    check("ne", operator.ne(1, 2.0), True)
    check("ge", operator.ge(1, 0), True)
    check("ge", operator.ge(1, 0.0), True)
    check("ge", operator.ge(1, 1), True)
    check("ge", operator.ge(1, 1.0), True)
    check("ge", operator.ge(1, 2), False)
    check("ge", operator.ge(1, 2.0), False)
    check("gt", operator.gt(1, 0), True)
    check("gt", operator.gt(1, 0.0), True)
    check("gt", operator.gt(1, 1), False)
    check("gt", operator.gt(1, 1.0), False)
    check("gt", operator.gt(1, 2), False)
    check("gt", operator.gt(1, 2.0), False)


class C(object):
    def __eq__(self, other: object) -> bool:
        raise SyntaxError
    def __ne__(self, other: object) -> bool:
        raise SyntaxError


def test_eq_ne_raises() -> None:
    try:
        operator.eq(C(), C())
    except SyntaxError:
        print("SyntaxError")
    try:
        operator.ne(C(), C())
    except SyntaxError:
        print("SyntaxError")


def test_arithmetic() -> None:
    check("abs", operator.abs(-1), 1)
    check("abs", operator.abs(1), 1)
    check("add", operator.add(3, 4), 7)
    check("and_", operator.and_(0xf, 0xa), 0xa)
    check("floordiv", operator.floordiv(5, 2), 2)
    check("truediv", operator.truediv(5, 2), 2.5)
    check("inv", operator.inv(4), -5)
    check("lshift", operator.lshift(5, 1), 10)
    check("lshift", operator.lshift(5, 0), 5)
    check("mod", operator.mod(5, 2), 1)
    check("mul", operator.mul(5, 2), 10)
    check("neg", operator.neg(5), -5)
    check("neg", operator.neg(-5), 5)
    check("neg", operator.neg(0), 0)
    check("neg", operator.neg(-0), 0)
    check("or_", operator.or_(0xa, 0x5), 0xf)
    check("pos", operator.pos(5), 5)
    check("pos", operator.pos(-5), -5)
    check("pos", operator.pos(0), 0)
    check("pos", operator.pos(-0), 0)
    check("pow", operator.pow(3,5), 3**5)
    check("rshift", operator.rshift(5, 1), 2)
    check("rshift", operator.rshift(5, 0), 5)
    check("sub", operator.sub(5, 2), 3)
    check("xor", operator.xor(0xb, 0xc), 0x7)
    try:
        operator.lshift(2, -1)
    except ValueError as e:
        print("ValueError:", e)
    try:
        operator.rshift(2, -1)
    except ValueError as e:
        print("ValueError:", e)


class M:
    def __matmul__(self, other: int) -> int:
        return other - 1


def test_matmul() -> None:
    check("M() @ 42", M() @ 42, 41)


class Seq1:
    def __init__(self, lst: list[int]) -> None:
        self.lst = lst
    def __len__(self) -> int:
        return len(self.lst)
    def __getitem__(self, i: int) -> int:
        return self.lst[i]
    def __add__(self, other: "Seq1") -> list[int]:
        return self.lst + other.lst


def test_concat() -> None:
    check("str", operator.concat('py', 'thon'), 'python')
    check("list", operator.concat([1, 2], [3, 4]), [1, 2, 3, 4])
    check("Seq1", operator.concat(Seq1([5, 6]), Seq1([7])), [5, 6, 7])


def test_delitem() -> None:
    a = [4, 3, 2, 1]
    check("None", operator.delitem(a, 1), None)
    check("a", a, [4, 2, 1])


def test_getitem() -> None:
    a = list(range(10))
    check("getitem", operator.getitem(a, 2), 2)


def test_indexOf() -> None:
    check("3", operator.indexOf([4, 3, 2, 1], 3), 1)
    try:
        operator.indexOf([4, 3, 2, 1], 0)
    except ValueError as e:
        print("ValueError:", e)
    it = iter('leave the iterator at exactly the position after the match')
    check("a", operator.indexOf(it, 'a'), 2)
    check("next", next(it), 'v')


def test_contains() -> None:
    check("2", operator.contains(list(range(4)), 2), True)
    check("5", operator.contains(list(range(4)), 5), False)


def test_setitem() -> None:
    a = list(range(3))
    check("None", operator.setitem(a, 0, 2), None)
    check("a", a, [2, 1, 2])
    try:
        operator.setitem(a, 4, 2)
    except IndexError as e:
        print("IndexError:", e)


class CB(object):
    def __bool__(self) -> bool:
        raise SyntaxError


def test_truth() -> None:
    try:
        operator.truth(CB())
    except SyntaxError:
        print("SyntaxError")
    check("5", operator.truth(5), True)
    check("[0]", operator.truth([0]), True)
    check("0", operator.truth(0), False)
    e: list[int] = []
    check("[]", operator.truth(e), False)


def test_is() -> None:
    a = b = 'xyzpdq'
    c = a[:3] + b[3:]
    check("is_", operator.is_(a, b), True)
    check("is_", operator.is_(a,c), False)
    check("is_not", operator.is_not(a, b), False)
    check("is_not", operator.is_not(a,c), True)


class CN:
    def __bool__(self) -> bool:
        raise SyntaxError


def test_not_() -> None:
    try:
        operator.not_(CN())
    except SyntaxError:
        print("SyntaxError")
    check("not 5", operator.not_(5), False)
    check("not [0]", operator.not_([0]), False)
    check("not 0", operator.not_(0), True)
    e: list[int] = []
    check("not []", operator.not_(e), True)


class A:
    def __init__(self) -> None:
        self.name = ''
        self.child: A | None = None


def test_attrgetter() -> None:
    a = A()
    a.name = 'arthur'
    f = operator.attrgetter('name')
    check("f(a)", f(a), 'arthur')


class R:
    def __init__(self) -> None:
        self.x = ''
        self.y = ''
        self.z = ''


def test_attrgetter_multiple() -> None:
    record = R()
    record.x = 'X'
    record.y = 'Y'
    record.z = 'Z'
    check("xzy", operator.attrgetter('x','z','y')(record), ('X', 'Z', 'Y'))


class A_2:
    def __init__(self, name: str) -> None:
        self.name = name
        self.child: A_2 | None = None


def test_attrgetter_recursive() -> None:
    a = A_2('arthur')
    a.child = A_2('thomas')
    f = operator.attrgetter('child.name')
    check("f(a)", f(a), 'thomas')
    f2 = operator.attrgetter('name', 'child.name')
    check("f(a)", f2(a), ('arthur', 'thomas'))


def test_itemgetter() -> None:
    a = 'ABCDE'
    f = operator.itemgetter(2)
    check("f(a)", f(a), 'C')
    f10 = operator.itemgetter(10)
    try:
        f10(a)
    except IndexError as e:
        print("IndexError:", e)
    d = {'key': 'val'}
    g = operator.itemgetter('key')
    check("g(d)", g(d), 'val')
    g2 = operator.itemgetter('nonkey')
    try:
        g2(d)
    except KeyError as e:
        print("KeyError:", e)
    inventory = [('apple', 3), ('banana', 2), ('pear', 5), ('orange', 1)]
    getcount = operator.itemgetter(1)
    check("map", list(map(getcount, inventory)), [3, 2, 5, 1])
    check("sorted", sorted(inventory, key=getcount),
        [('orange', 1), ('banana', 2), ('apple', 3), ('pear', 5)])
    data = list(map(str, range(20)))
    check("multiple", operator.itemgetter(2,10,5)(data), ('2', '10', '5'))
    t = tuple('abcde')
    check("-1", operator.itemgetter(-1)(t), 'e')
    check("list", operator.itemgetter(0)(['a', 'b', 'c']), 'a')


class A_3:
    def foo(self, *args, **kwds):
        return args[0] + args[1]
    def bar(self, f=42):
        return f
    def baz(*args, **kwds):
        return kwds['name'], kwds['self']


def test_methodcaller() -> None:
    a = A_3()
    f = operator.methodcaller('foo', 1, 2)
    check("foo", f(a), 3)
    f = operator.methodcaller('bar')
    check("bar", f(a), 42)
    f = operator.methodcaller('bar', f=5)
    check("bar f=5", f(a), 5)


class A_4:
    def baz(*args, **kwds):
        return kwds['name'], kwds['self']


def test_methodcaller_baz() -> None:
    a = A_4()
    f = operator.methodcaller('baz', name='spam', self='eggs')
    check("baz", f(a), ('spam', 'eggs'))


test_comparisons()
test_eq_ne_raises()
test_arithmetic()
test_matmul()
test_concat()
test_delitem()
test_getitem()
test_indexOf()
test_contains()
test_setitem()
test_truth()
test_is()
test_not_()
test_attrgetter()
test_attrgetter_multiple()
test_attrgetter_recursive()
test_itemgetter()
test_methodcaller()
test_methodcaller_baz()
