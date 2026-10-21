# Adapted from CPython 3.13.16 Lib/test/test_scope.py, class ScopeTests: testScopeOfGlobalStmt
# (examples I to IV), testNonLocalFunction, testGlobalInParallelNestedFunctions and
# testNestedNonLocal, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b. The code upstream runs with exec() runs here as module code, where its names are module
# globals as they are in exec()'s namespace; each example's f is renamed (f_I to f_IV), as a
# module binds a function's name once, and testGlobalInParallelNestedFunctions' f, which returns
# two closures, is nested in its test function (a module-level def without parameters needs a
# return annotation, and a tuple display of closures does not convert to the annotation's
# Callables: existing issue #245).
# EXCLUDED upstream cases (see also tests/programs/upstream/upstream_scope_closures.py):
# - testScopeOfGlobalStmt's class Global: a global statement in a class body (rejected)
# - testUnboundLocal_AugAssign: `global_x += 1` without `global` in a function (rejected at compile
#   time: a local read before its first assignment, where CPython raises UnboundLocalError)
# - testNonLocalMethod, testNonLocalClass, testClassAndGlobal: classes inside functions (rejected),
#   a nonlocal or global statement in a class body, and locals()
# - testNonLocalGenerator: a generator function (yield)


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


# testScopeOfGlobalStmt: examples posted by Samuele Pedroni to python-dev on 3/1/2001

# I
x = 7
def f_I() -> int:
    x = 1
    def g():
        global x
        def i():
            def h():
                return x
            return h()
        return i()
    return g()
check("I: f()", f_I(), 7)
check("I: x", x, 7)

# II
x = 7
def f_II() -> int:
    x = 1
    def g():
        x = 2
        def i():
            def h():
                return x
            return h()
        return i()
    return g()
check("II: f()", f_II(), 2)
check("II: x", x, 7)

# III
x = 7
def f_III() -> int:
    x = 1
    def g():
        global x
        x = 2
        def i():
            def h():
                return x
            return h()
        return i()
    return g()
check("III: f()", f_III(), 2)
check("III: x", x, 2)

# IV
x = 7
def f_IV() -> int:
    x = 3
    def g():
        global x
        x = 2
        def i():
            def h():
                return x
            return h()
        return i()
    return g()
check("IV: f()", f_IV(), 2)
check("IV: x", x, 2)


def testNonLocalFunction() -> None:

    def f(x):
        def inc():
            nonlocal x
            x += 1
            return x
        def dec():
            nonlocal x
            x -= 1
            return x
        return inc, dec

    inc, dec = f(0)
    check("inc()", inc(), 1)
    check("inc()", inc(), 2)
    check("dec()", dec(), 1)
    check("dec()", dec(), 0)


def testGlobalInParallelNestedFunctions() -> None:
    # A symbol table bug leaked the global statement from one
    # function to other nested functions in the same block.
    # This test verifies that a global statement in the first
    # function does not affect the second function.
    def f():
        y = 1
        def g():
            global y
            return y
        def h():
            return y + 1
        return g, h
    g, h = f()
    result9 = g()
    result2 = h()
    check("result2", result2, 2)
    check("result9", result9, 9)


def testNestedNonLocal() -> None:

    def f(x):
        def g():
            nonlocal x
            x -= 2
            def h():
                nonlocal x
                x += 4
                return x
            return h
        return g

    g = f(1)
    h = g()
    check("h()", h(), 3)


testNonLocalFunction()
y = 9
testGlobalInParallelNestedFunctions()
testNestedNonLocal()
