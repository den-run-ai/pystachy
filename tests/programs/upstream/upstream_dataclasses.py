# Adapted from CPython 3.13.16 Lib/test/test_dataclasses/__init__.py: TestCase's
# test_one_field_no_default (with test_named_init_params), test_two_fields_one_default,
# test_0_field_compare, test_1_field_compare, test_simple_compare, test_compare_subclasses,
# test_field_no_default, test_not_in_compare, test_not_in_repr, test_hash_field_rules,
# test_post_init and test_default_factory; TestRepr.test_repr; TestHash's test_unsafe_hash,
# test_0_field_hash and test_1_field_hash; TestFrozen's test_frozen and test_inherit;
# TestReplace's test and test_frozen; and TestKeywordArgs' test_KW_ONLY and test_defaults;
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function (test_hash is TestHash's three, test_frozen_inherit
# TestFrozen.test_inherit, test_replace TestReplace's two, test_KW_ONLY_defaults
# TestKeywordArgs.test_defaults); assertEqual(a, b), assertTrue(x) and assertLess(a, b) & co
# print and assert, assertRaises a try statement that prints the exception. The dataclasses that
# upstream defines in each method are module classes, where a later one of the same name is
# renamed C_2, C0_2, ... (and so are the reprs expected of them); the subtests of one method
# over several classes are one class each (test_hash_field_rules' C1 to C6), and a test method's
# loop over [C0, C1] is written out. test_simple_compare_order and test_compare_subclasses_order
# are the order=True parts (test_simple_compare's list of lambdas is annotated
# list[Callable[[C, C], bool]]; test_compare_subclasses' TypeError is of order=True classes
# here). list fields are list[int]; test_default_factory's shared list l is a module global.
# A repr() shows the class's name, where upstream's shows its qualified name
# (TestCase.test_not_in_repr.<locals>.C()).
# EXCLUDED upstream cases:
# - fields(), asdict(), astuple(), make_dataclass(), is_dataclass(), InitVar, ClassVar,
#   slots=True, __match_args__, __dict__/vars(), __annotations__, the class __dict__ checks of
#   test_eq_order, and the TypeErrors and ValueErrors that @dataclass raises as CPython creates
#   a class (non-default after default, mutable defaults, frozen/non-frozen inheritance, ...):
#   rejected at compile time here
# - test_1_field_compare's and test_simple_compare's `<` of order=False classes (a compile-time
#   error here, with CPython's message "'<' not supported between instances of 'C0' and 'C0'":
#   tests/errors/upstream/upstream_dataclasses_order_false.py),
#   test_0_field_compare's likewise
# - test_init_in_order (an untyped __setattr__ override and a list of mixed tuples),
#   test_default_factory_with_no_init and test_default_factory_not_called_if_value_given (Mock),
#   test_post_init_super/staticmethod/classmethod, test_field_default (object() defaults and
#   del of a field), TestDescriptors, TestStringAnnotations, TestSlots, TestMakeDataclass,
#   TestAbstract, TestMatchArgs, pickling and deepcopy tests
from typing import Callable

from dataclasses import dataclass, field, replace, KW_ONLY, FrozenInstanceError


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


class CustomError(Exception): pass


@dataclass
class C1:
    x: int


def test_one_field_no_default() -> None:
    o = C1(42)
    check("o.x", o.x, 42)
    o = C1(x=32)
    check("o.x", o.x, 32)


@dataclass
class C2:
    x: int
    y: int = 0


def test_two_fields_one_default() -> None:
    o = C2(3)
    check("(o.x, o.y)", (o.x, o.y), (3, 0))


@dataclass
class C0:
    pass


@dataclass(order=True)
class C:
    pass


def test_0_field_compare() -> None:
    check("C0() == C0()", C0() == C0(), True)
    check("C() <= C()", C() <= C(), True)
    check("C() >= C()", C() >= C(), True)


@dataclass
class C0_2:
    x: int


@dataclass(order=False)
class C1_2:
    x: int


@dataclass(order=True)
class C_2:
    x: int


def test_1_field_compare() -> None:
    check("C0_2 ==", C0_2(1) == C0_2(1), True)
    check("C0_2 !=", C0_2(0) != C0_2(1), True)
    check("C1_2 ==", C1_2(1) == C1_2(1), True)
    check("C1_2 !=", C1_2(0) != C1_2(1), True)
    check("<", C_2(0) < C_2(1), True)
    check("<=", C_2(0) <= C_2(1), True)
    check("<=", C_2(1) <= C_2(1), True)
    check(">", C_2(1) > C_2(0), True)
    check(">=", C_2(1) >= C_2(0), True)
    check(">=", C_2(1) >= C_2(1), True)


@dataclass
class C0_3:
    x: int
    y: int


def test_simple_compare() -> None:
    check("==", C0_3(0, 0) == C0_3(0, 0), True)
    check("==", C0_3(1, 2) == C0_3(1, 2), True)
    check("!=", C0_3(1, 0) != C0_3(0, 0), True)
    check("!=", C0_3(1, 0) != C0_3(1, 1), True)


@dataclass(order=True)
class C_3:
    x: int
    y: int


def test_simple_compare_order() -> None:
    fns: list[Callable[[C_3, C_3], bool]] = [lambda a, b: a == b,
               lambda a, b: a <= b,
               lambda a, b: a >= b]
    for fn in fns:
        check("fn", fn(C_3(0, 0), C_3(0, 0)), True)

    fns = [lambda a, b: a < b,
               lambda a, b: a <= b,
               lambda a, b: a != b]
    for fn in fns:
        check("fn", fn(C_3(0, 0), C_3(0, 1)), True)
        check("fn", fn(C_3(0, 1), C_3(1, 0)), True)
        check("fn", fn(C_3(1, 0), C_3(1, 1)), True)

    fns = [lambda a, b: a > b,
               lambda a, b: a >= b,
               lambda a, b: a != b]
    for fn in fns:
        check("fn", fn(C_3(0, 1), C_3(0, 0)), True)
        check("fn", fn(C_3(1, 0), C_3(0, 1)), True)
        check("fn", fn(C_3(1, 1), C_3(1, 0)), True)


@dataclass
class B:
    i: int


@dataclass
class C_4(B):
    pass


def test_compare_subclasses() -> None:
    check("==", B(0) == C_4(0), False)
    check("!=", B(0) != C_4(0), True)


@dataclass(order=True)
class B_2:
    i: int


@dataclass(order=True)
class C_5(B_2):
    pass


def test_compare_subclasses_order() -> None:
    try:
        B_2(0) < C_5(0)
    except TypeError as e:
        print("TypeError:", e)


@dataclass
class C_6:
    x: int = field()


def test_field_no_default() -> None:
    check("C_6(5).x", C_6(5).x, 5)


@dataclass
class C_7:
    x: int = 0
    y: int = field(compare=False, default=4)


def test_not_in_compare() -> None:
    check("==", C_7() == C_7(0, 20), True)
    check("==", C_7(1, 10) == C_7(1, 20), True)
    check("!=", C_7(3) != C_7(4, 10), True)
    check("!=", C_7(3, 10) != C_7(4, 10), True)


@dataclass
class C_8:
    x: int = field(repr=False)


@dataclass
class D:
    x: int = field(repr=False)
    y: int


def test_not_in_repr() -> None:
    check("repr", repr(C_8(10)), 'C_8()')
    check("repr", repr(D(10, 20)), 'D(y=20)')


@dataclass(unsafe_hash=True)
class C1_3:
    x: int = field(compare=False, hash=True, default=5)


@dataclass(unsafe_hash=True)
class C2_2:
    x: int = field(compare=True, hash=True, default=5)


@dataclass(unsafe_hash=True)
class C3:
    x: int = field(compare=False, hash=False, default=5)


@dataclass(unsafe_hash=True)
class C4:
    x: int = field(compare=True, hash=False, default=5)


@dataclass(unsafe_hash=True)
class C5:
    x: int = field(compare=False, hash=None, default=5)


@dataclass(unsafe_hash=True)
class C6:
    x: int = field(compare=True, hash=None, default=5)


def test_hash_field_rules() -> None:
    check("C1_3", hash(C1_3(5)) == hash((5,)), True)
    check("C2_2", hash(C2_2(5)) == hash((5,)), True)
    check("C3", hash(C3(5)) == hash(()), True)
    check("C4", hash(C4(5)) == hash(()), True)
    check("C5", hash(C5(5)) == hash(()), True)
    check("C6", hash(C6(5)) == hash((5,)), True)


@dataclass
class C1_4:
    def __post_init__(self):
        raise CustomError()


@dataclass
class C2_3:
    i: int = 10
    def __post_init__(self):
        if self.i == 10:
            raise CustomError()


@dataclass(init=False)
class C3_2:
    def __post_init__(self):
        raise CustomError()


@dataclass
class C4_2:
    x: int = 0
    def __post_init__(self):
        self.x *= 2


@dataclass(frozen=True)
class C5_2:
    x: int = 0
    def __post_init__(self):
        self.x *= 2


def test_post_init() -> None:
    try:
        C1_4()
    except CustomError:
        print("CustomError")
    try:
        C2_3()
    except CustomError:
        print("CustomError")
    C2_3(5)
    C3_2()
    check("C4_2().x", C4_2().x, 0)
    check("C4_2(2).x", C4_2(2).x, 4)
    try:
        C5_2()
    except FrozenInstanceError as e:
        print("FrozenInstanceError", e)


@dataclass
class C1_5:
    x: int
    y: list[int] = field(default_factory=list)


l: list[int] = []


@dataclass
class C2_4:
    x: int
    y: list[int] = field(default_factory=lambda: l)


@dataclass
class C3_3:
    x: list[int] = field(default_factory=list, repr=False)


@dataclass(unsafe_hash=True)
class C4_3:
    x: list[int] = field(default_factory=list, hash=False)


@dataclass
class C5_3:
    x: list[int] = field(default_factory=list, init=False)


@dataclass
class C6_2:
    x: list[int] = field(default_factory=list, compare=False)


def test_default_factory() -> None:
    e: list[int] = []
    c0 = C1_5(3)
    c1 = C1_5(3)
    check("c0.x", c0.x, 3)
    check("c0.y", c0.y, e)
    check("c0 == c1", c0 == c1, True)
    check("is not", c0.y is not c1.y, True)

    c2 = C2_4(3)
    c3 = C2_4(3)
    check("c0.x", c2.x, 3)
    check("c0.y", c2.y, e)
    check("c0 == c1", c2 == c3, True)
    check("is", c2.y is c3.y, True)

    check("repr", repr(C3_3()), 'C3_3()')
    check("C3_3().x", C3_3().x, e)
    check("hash", hash(C4_3()) == hash(()), True)
    check("C5_3().x", C5_3().x, e)
    check("C6_2", C6_2() == C6_2([1]), True)


@dataclass
class B_3:
    x: int


@dataclass
class C_9(B_3):
    y: int = 10


@dataclass
class D_2(C_9):
    x: int = 20


def test_repr() -> None:
    o = C_9(4)
    check("repr", repr(o), 'C_9(x=4, y=10)')
    check("repr", repr(D_2()), 'D_2(x=20, y=10)')


@dataclass(unsafe_hash=True)
class C_10:
    x: int
    y: str


@dataclass(frozen=True)
class F0:
    pass


@dataclass(unsafe_hash=True)
class U0:
    pass


@dataclass(frozen=True)
class F1:
    x: int


@dataclass(unsafe_hash=True)
class U1:
    x: int


def test_hash() -> None:
    check("unsafe_hash", hash(C_10(1, 'foo')) == hash((1, 'foo')), True)
    check("F0", hash(F0()) == hash(()), True)
    check("U0", hash(U0()) == hash(()), True)
    check("F1", hash(F1(4)) == hash((4,)), True)
    check("F1", hash(F1(42)) == hash((42,)), True)
    check("U1", hash(U1(4)) == hash((4,)), True)
    check("U1", hash(U1(42)) == hash((42,)), True)


@dataclass(frozen=True)
class C_11:
    i: int


def test_frozen() -> None:
    c = C_11(10)
    check("c.i", c.i, 10)
    try:
        c.i = 5
    except FrozenInstanceError as e:
        print("FrozenInstanceError", e)
    check("c.i", c.i, 10)
    try:
        del c.i
    except FrozenInstanceError as e:
        print("FrozenInstanceError", e)
    check("c.i", c.i, 10)


@dataclass(frozen=True)
class C_12:
    i: int


@dataclass(frozen=True)
class D_3(C_12):
    j: int


def test_frozen_inherit() -> None:
    d = D_3(0, 10)
    try:
        d.i = 5
    except FrozenInstanceError as e:
        print("FrozenInstanceError", e)
    try:
        d.j = 6
    except FrozenInstanceError as e:
        print("FrozenInstanceError", e)
    check("d.i", d.i, 0)
    check("d.j", d.j, 10)


@dataclass(frozen=True)
class C_13:
    x: int
    y: int


@dataclass(frozen=True)
class D_4:
    x: int
    y: int
    z: int = field(init=False, default=10)
    t: int = field(init=False, default=100)


def test_replace() -> None:
    c = C_13(1, 2)
    c1 = replace(c, x=3)
    check("c1.x", c1.x, 3)
    check("c1.y", c1.y, 2)
    d = D_4(1, 2)
    d1 = replace(d, x=3)
    check("d", (d.x, d.y, d.z, d.t), (1, 2, 10, 100))
    check("d1", (d1.x, d1.y, d1.z, d1.t), (3, 2, 10, 100))
    try:
        d1.x = 3
    except FrozenInstanceError as e:
        print("FrozenInstanceError", e)


@dataclass
class A:
    a: int
    _: KW_ONLY
    b: int
    c: int


@dataclass(kw_only=True)
class B_4:
    a: int
    _: KW_ONLY
    b: int
    c: int


@dataclass
class C_14:
    a: int
    _: KW_ONLY
    b: int
    c: int = field(kw_only=False)


def test_KW_ONLY() -> None:
    A(3, c=5, b=4)
    B_4(a=3, b=4, c=5)
    c = C_14(1, 2, b=3)
    check("c.a", c.a, 1)
    check("c.b", c.b, 3)
    check("c.c", c.c, 2)
    c = C_14(1, b=3, c=2)
    check("c.a", c.a, 1)
    check("c.b", c.b, 3)
    check("c.c", c.c, 2)
    c = C_14(c=2, b=3, a=1)
    check("c.a", c.a, 1)
    check("c.b", c.b, 3)
    check("c.c", c.c, 2)


@dataclass
class A_2:
    a: int = 0
    _: KW_ONLY
    b: int
    c: int = 1
    d: int


def test_KW_ONLY_defaults() -> None:
    a = A_2(d=4, b=3)
    check("a.a", a.a, 0)
    check("a.b", a.b, 3)
    check("a.c", a.c, 1)
    check("a.d", a.d, 4)


test_one_field_no_default()
test_two_fields_one_default()
test_0_field_compare()
test_1_field_compare()
test_simple_compare()
test_simple_compare_order()
test_compare_subclasses()
test_compare_subclasses_order()
test_field_no_default()
test_not_in_compare()
test_not_in_repr()
test_hash_field_rules()
test_post_init()
test_default_factory()
test_repr()
test_hash()
test_frozen()
test_frozen_inherit()
test_replace()
test_KW_ONLY()
test_KW_ONLY_defaults()
