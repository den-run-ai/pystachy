# Adapted from CPython 3.13.16 Lib/test/test_scope.py, class ScopeTests: testSimpleNesting,
# testExtraNesting, testSimpleAndRebinding, testNestingGlobalNoFree, testNestingPlusFreeRefToGlobal,
# testNearestEnclosingScope, testFreeVarInMethod (its unnested class), testCellIsKwonlyArg,
# testRecursion, testLambdas, testComplexDefinitions and testTopIsNotSignificant,
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b. Annotations are added where the subset needs them (a function without parameters
# returns None unless annotated). testNestingGlobalNoFree and testLambdas' f3 read a name the
# upstream comment calls a "plain old global": here it is a module global (assigned after the
# closures are made, read when they run), as in the module-level original of this file; the
# in-method form, a cell assigned after the def that reads it, is rejected (below).
# EXCLUDED upstream cases (see also tests/programs/upstream/upstream_scope_global_nonlocal.py):
# - testNestingThroughClass, testBoundAndFree, testFreeVarInMethod's nested class: a class
#   inside a function (rejected: no class scope inside functions)
# - testMixedFreevarsAndCellvars; testNestingGlobalNoFree and testLambdas' f3 in their in-method
#   form: a closure that reads a variable of the function around it assigned only after its def
#   (rejected: "reads 'y', which may not be assigned yet where it is defined")
# - testCellIsArgAndEscapes, testCellIsLocalAndEscapes: __closure__ and cell objects
# - testUnboundLocal, testUnboundLocal_AfterDel: a read before the assignment and a del of a
#   variable a closure reads (rejected at compile time, where CPython raises UnboundLocalError
#   or NameError)
# - testUnoptimizedNamespaces: compile() of `from sys import *` in a function; its first and
#   third sources are tests/errors/upstream/upstream_scope_import_star.py and _star_outer.py (the same
#   SyntaxError, at CPython's line), the other two give that error too
# - testLeaks, testCellLeak, testFreeingCell: __del__, weakref and gc
# - testLocalsFunction, testLocalsClass, testLocalsClass_WithTrace, testClassNamespaceOverridesClosure,
#   testInteractionWithTraceFunc: locals(), sys.settrace() and classes inside functions
# - testEvalExecFreeVars, testEvalFreeVars: eval() and exec()
# - testListCompLocalVars: a read of an unbound global (a compile-time error here)
# - test_multiple_nesting: a class inside a method (and name mangling of its parameter)


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def testSimpleNesting() -> None:

    def make_adder(x):
        def adder(y):
            return x + y
        return adder

    inc = make_adder(1)
    plus10 = make_adder(10)

    check("inc(1)", inc(1), 2)
    check("plus10(-2)", plus10(-2), 8)


def testExtraNesting() -> None:

    def make_adder2(x):
        def extra(): # check freevars passing through non-use scopes
            def adder(y):
                return x + y
            return adder
        return extra()

    inc = make_adder2(1)
    plus10 = make_adder2(10)

    check("inc(1)", inc(1), 2)
    check("plus10(-2)", plus10(-2), 8)


def testSimpleAndRebinding() -> None:

    def make_adder3(x):
        def adder(y):
            return x + y
        x = x + 1 # check tracking of assignment to x in defining scope
        return adder

    inc = make_adder3(0)
    plus10 = make_adder3(9)

    check("inc(1)", inc(1), 2)
    check("plus10(-2)", plus10(-2), 8)


# testNestingGlobalNoFree, with global_x a module global ("plain old globals")
def testNestingGlobalNoFree() -> None:
    global global_x

    def make_adder4(): # XXX add exta level of indirection
        def nest():
            def nest():
                def adder(y):
                    return global_x + y # check that plain old globals work
                return adder
            return nest()
        return nest()

    global_x = 1
    adder = make_adder4()
    check("adder(1)", adder(1), 2)

    global_x = 10
    check("adder(-2)", adder(-2), 8)


global_x = 0
global_nest_x = 0


def testNestingPlusFreeRefToGlobal() -> None:

    def make_adder6(x):
        global global_nest_x
        def adder(y):
            return global_nest_x + y
        global_nest_x = x
        return adder

    inc = make_adder6(1)
    plus10 = make_adder6(10)

    check("inc(1)", inc(1), 11) # there's only one global
    check("plus10(-2)", plus10(-2), 8)


def testNearestEnclosingScope() -> None:

    def f(x):
        def g(y):
            x = 42 # check that this masks binding in f()
            def h(z):
                return x + z
            return h
        return g(2)

    test_func = f(10)
    check("test_func(5)", test_func(5), 47)


# testFreeVarInMethod: "this class is not nested, so the rules are different"
method_and_var = "var"
class Test:
    # this class is not nested, so the rules are different
    def method_and_var(self) -> str:
        return "method"
    def test(self) -> str:
        return method_and_var
    def actual_global(self) -> str:
        return str("global")
    def str(self) -> str:
        return str(self)


def testFreeVarInMethod() -> None:
    t = Test()
    check("t.test()", t.test(), "var")
    check("t.method_and_var()", t.method_and_var(), "method")
    check("t.actual_global()", t.actual_global(), "global")


def testCellIsKwonlyArg() -> None:
    # Issue 1409: Initialisation of a cell value,
    # when it comes from a keyword-only parameter
    def foo(*, a=17):
        def bar():
            return a + 5
        return bar() + 3

    check("foo(a=42)", foo(a=42), 50)
    check("foo()", foo(), 25)


def testRecursion() -> None:

    def f(x):
        def fact(n):
            if n == 0:
                return 1
            else:
                return n * fact(n - 1)
        if x >= 0:
            return fact(x)
        else:
            raise ValueError("x must be >= 0")

    check("f(6)", f(6), 720)


# testLambdas, with f3's global_x a module global ("plain old globals")
def testLambdas() -> None:
    global global_x

    f1 = lambda x: lambda y: x + y
    inc = f1(1)
    plus10 = f1(10)
    check("inc(1)", inc(1), 2)
    check("plus10(5)", plus10(5), 15)

    f2 = lambda x: (lambda : lambda y: x + y)()
    inc2 = f2(1)
    plus10_2 = f2(10)
    check("inc(1)", inc2(1), 2)
    check("plus10(5)", plus10_2(5), 15)

    f3 = lambda x: lambda y: global_x + y
    global_x = 1
    inc3 = f3(None)
    check("inc(2)", inc3(2), 3)

    f8 = lambda x, y, z: lambda a, b, c: lambda : z * (b + y)
    g = f8(1, 2, 3)
    h = g(2, 4, 6)
    check("h()", h(), 18)


def testComplexDefinitions() -> None:

    def makeReturner(*lst):
        def returner():
            return lst
        return returner

    check("makeReturner(1,2,3)()", makeReturner(1,2,3)(), (1,2,3))

    def makeReturner2(**kwargs):
        def returner():
            return kwargs
        return returner

    check("makeReturner2(a=11)()['a']", makeReturner2(a=11)()['a'], 11)


def testTopIsNotSignificant() -> None:
    # See #9997.
    def top(a):
        pass
    def b():
        global a
    print("testTopIsNotSignificant compiles")


testSimpleNesting()
testExtraNesting()
testSimpleAndRebinding()
testNestingGlobalNoFree()
testNestingPlusFreeRefToGlobal()
testNearestEnclosingScope()
testFreeVarInMethod()
testCellIsKwonlyArg()
testRecursion()
testLambdas()
testComplexDefinitions()
testTopIsNotSignificant()
