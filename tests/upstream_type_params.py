# Adapted from CPython 3.13.16 Lib/test/test_type_params.py: TypeParamsInvalidTest's
# test_name_non_collision_02 to _9 and _13, TypeParamsNonlocalTest.test_nonlocal_allowed,
# TypeParamsAccessTest's test_shadowing_nonlocal and test_super,
# TypeParamsComplexCallsTest.test_defaults, TypeParamsTraditionalTypeVarsTest.test_traditional_03
# and TypeParamsManglingTest's test_no_leaky_mangling_in_module and
# test_no_leaky_mangling_in_function; commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b. The code that upstream run_code()s (or defines in the method) is at the module's top
# level, where a later test's function or class of the same name is renamed (func_2, ClassA_2,
# ...); the asserts on __type_params__ and __name__ of the type variables are left out (below).
# test_traditional_03 calls the function it defines. test_no_leaky_mangling_in_function's class
# is at the module's top level (no class statement in a function), and the mangling tests' class
# X is Y (and _X_foo _Y_foo), as test_name_non_collision_13 binds the global X.
# EXCLUDED upstream cases:
# - runtime introspection of type parameters and aliases, which Pystachy resolves at compile time
#   (a type alias or type variable used as a value is rejected, as documented):
#   __type_params__, __bound__, __constraints__, __default__, __annotations__, __parameters__,
#   __value__, __qualname__ (rejected: "type object 'GlobalGenericClass' has no attribute
#   '__qualname__'"), types.get_original_bases(): all of Lib/test/test_type_aliases.py, and in
#   test_type_params.py TypeParamsAccessTest's other tests, TypeParamsLazyEvaluationTest,
#   TypeParamsClassScopeTest, DynamicClassTest, TypeParamsManglingTest.test_mangling,
#   TypeParamsTypeVarTest, TypeParamsTypeVarTupleTest, TypeParamsTypeVarParamSpecTest,
#   TypeParamsTypeParamsDunder, TypeParamsPickleTest, TypeParamsWeakRefTest,
#   TypeParamsRuntimeTest and DefaultsTest (but test_starred_invalid, below)
# - test_name_non_collision_10 (__annotations__ of a class body)
# - test_no_leaky_mangling_in_function's class in a function (rejected: "a class inside a
#   function is not supported"), test_no_leaky_mangling_in_class and test_no_mangling_in_bases
#   (class bodies, __init_subclass__), test_type_params_are_mangled, test_no_mangling_in_nested_scopes,
#   test_class_base_containing_lambda, test_complex_base, test_starargs_base,
#   test_incorrect_mro_explicit_object, test_traditional_01 and _02 (bases of generic classes)
# - SyntaxErrors (check_syntax_error()): Pystachy reports test_name_collisions',
#   test_disallowed_expressions', test_typevartuple_01's, test_paramspec_01's and
#   test_type_aliases.py's with CPython's messages at compile time (checked with
#   tools/syntax_sweep.py), but accepts DefaultsTest.test_starred_invalid's
#   `type Alias[T = *int] = int` and `type Alias[**P = *int] = int` (a bug)
from typing import TypeVar


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def func[A](A): return A


def test_name_non_collision_02() -> None:
    check("func(1)", func(1), 1)


def func_2[A](*A): return A


def test_name_non_collision_03() -> None:
    check("func_2(1)", func_2(1), (1,))


class ClassA:
    def func[__A](self, __A): return __A


def test_name_non_collision_04() -> None:
    check("ClassA().func(1)", ClassA().func(1), 1)


class ClassA_2:
    def func[_ClassA__A](self, __A): return __A


def test_name_non_collision_05() -> None:
    check("ClassA_2().func(1)", ClassA_2().func(1), 1)


class ClassA_3[X]:
    def func(self, X): return X


def test_name_non_collision_06() -> None:
    check("ClassA_3().func(1)", ClassA_3().func(1), 1)


class ClassA_4[X]:
    def func(self):
        X = 1
        return X


def test_name_non_collision_07() -> None:
    check("ClassA_4().func()", ClassA_4().func(), 1)


class ClassA_5[X]:
    def func(self):
        return [X for X in [1, 2]]


def test_name_non_collision_08() -> None:
    check("ClassA_5().func()", ClassA_5().func(), [1, 2])


class ClassA_6[X]:
    def func[X](self):
        ...


def test_name_non_collision_9() -> None:
    print(ClassA_6().func())


X = 1


def outer():
    def inner[X]():
        global X
        X = 2
    return inner


def test_name_non_collision_13() -> None:
    check("X", X, 1)
    outer()()
    check("X", X, 2)


def func_3[T]():
    T = "func_3"
    def inner():
        nonlocal T
        T = "inner"
    inner()
    assert T == "inner"
    print(T)


def test_nonlocal_allowed() -> None:
    func_3()


def outer_2[T]():
    T = "outer_2"
    def inner():
        nonlocal T
        T = "inner"
        return T
    return lambda: T, inner


def test_shadowing_nonlocal() -> None:
    getter, inner = outer_2()
    check("getter()", getter(), "outer_2")
    check("inner()", inner(), "inner")
    check("getter()", getter(), "inner")


class Base:
    def meth(self):
        return "base"


class Child(Base):
    # Having int in the annotation ensures the class gets cells for both
    # __class__ and __classdict__
    def meth[T](self, arg: int) -> T:
        return super().meth() + "child"


def test_super() -> None:
    c = Child()
    check("c.meth(1)", c.meth(1), "basechild")


def func_4[T](a: T = "a", *, b: T = "b"):
    return (a, b)


def test_defaults() -> None:
    check("func_4()", func_4(), ("a", "b"))
    check("func_4(1)", func_4(1), (1, "b"))
    check("func_4(b=2)", func_4(b=2), ("a", 2))


S = TypeVar("S")


def func_5[T](a: T, b: S) -> T | S:
    return a


def test_traditional_03() -> None:
    check("func_5(1, 'x')", func_5(1, 'x'), 1)


# test_no_leaky_mangling_in_module (upstream run_code()s it as a module)
__before = "before"


class Y[T]: pass


__after = "after"
check("__before", __before, "before")
check("__after", __after, "after")


def f():
    _Y_foo = 2
    __foo = 1
    return __foo


def test_no_leaky_mangling_in_function() -> None:
    check("f()", f(), 1)


test_name_non_collision_02()
test_name_non_collision_03()
test_name_non_collision_04()
test_name_non_collision_05()
test_name_non_collision_06()
test_name_non_collision_07()
test_name_non_collision_08()
test_name_non_collision_9()
test_name_non_collision_13()
test_nonlocal_allowed()
test_shadowing_nonlocal()
test_super()
test_defaults()
test_traditional_03()
test_no_leaky_mangling_in_function()
