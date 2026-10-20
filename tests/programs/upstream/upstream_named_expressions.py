# Adapted from CPython 3.13.16 Lib/test/test_named_expressions.py, classes
# NamedExpressionAssignmentTest (test_named_expression_assignment_01 to _18) and
# NamedExpressionScopeTest: test_named_expression_scope_02 to _11, _17 to _25,
# test_named_expression_variable_reuse_in_comprehensions, test_named_expression_global_scope,
# test_named_expression_global_scope_no_global_keyword, test_named_expression_nonlocal_scope and
# test_named_expression_nonlocal_scope_no_nonlocal_keyword; commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) and assertTrue(x) print
# and assert, self.fail() an assert. test_named_expression_assignment_18's TwoDimensionalList and
# test_named_expression_scope_25's module code (upstream exec()s it) are at the module's top
# level. test_named_expression_variable_reuse_in_comprehensions exec()s eight snippets: the four
# "global" ones run at the module's top level, the four "nonlocal" ones are reuse_*_nonlocal.
# sentinel = object() is an object of a class of its own, and GLOBAL_VAR, an annotated global.
# test_named_expression_assignment_12's and test_named_expression_scope_04's lists of an int
# and a float are annotated list[list[int | float]], and so is _12's expected value.
# EXCLUDED upstream cases:
# - NamedExpressionInvalidTest (SyntaxErrors of exec()'d code): Pystachy reports the same
#   errors with CPython's messages at compile time (checked with tools/syntax_sweep.py)
# - test_named_expression_scope_01 and _25's exec() itself; test_named_expression_scope_in_genexp
#   (a generator expression as a value is rejected: "a generator expression is only supported as
#   the argument of sum(), min(), max(), sorted(), list(), tuple(), any(), all(), math.fsum(),
#   math.prod(), str.join() or list.extend(), or as the value assigned to a list slice") and its
#   locals(); test_named_expression_scope_mangled_names (a class in a method, name mangling)
def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def test_named_expression_assignment_01() -> None:
    (a := 10)
    check("a", a, 10)


def test_named_expression_assignment_02() -> None:
    a = 20
    (a := a)
    check("a", a, 20)


def test_named_expression_assignment_03() -> None:
    (total := 1 + 2)
    check("total", total, 3)


def test_named_expression_assignment_04() -> None:
    (info := (1, 2, 3))
    check("info", info, (1, 2, 3))


def test_named_expression_assignment_05() -> None:
    (x := 1, 2)
    check("x", x, 1)


def test_named_expression_assignment_06() -> None:
    (z := (y := (x := 0)))
    check("x", x, 0)
    check("y", y, 0)
    check("z", z, 0)


def test_named_expression_assignment_07() -> None:
    (loc := (1, 2))
    check("loc", loc, (1, 2))


def test_named_expression_assignment_08() -> None:
    if spam := "eggs":
        check("spam", spam, "eggs")
    else: assert False, "variable was not assigned using named expression"


def test_named_expression_assignment_09() -> None:
    if True and (spam := True):
        check("spam", spam, True)
    else: assert False, "variable was not assigned using named expression"


def test_named_expression_assignment_10() -> None:
    if (match := 10) == 10:
        check("match", match, 10)
    else: assert False, "variable was not assigned using named expression"


def test_named_expression_assignment_11() -> None:
    def spam(a):
        return a
    input_data = [1, 2, 3]
    res = [(x, y, x/y) for x in input_data if (y := spam(x)) > 0]
    check("res", res, [(1, 1, 1.0), (2, 2, 1.0), (3, 3, 1.0)])


def test_named_expression_assignment_12() -> None:
    def spam(a):
        return a
    res: list[list[int | float]] = [[y := spam(x), x/y] for x in range(1, 5)]
    expected: list[list[int | float]] = [[1, 1.0], [2, 1.0], [3, 1.0], [4, 1.0]]
    check("res", res, expected)


def test_named_expression_assignment_13() -> None:
    length = len(lines := [1, 2])
    check("length", length, 2)
    check("lines", lines, [1,2])


def test_named_expression_assignment_14() -> None:
    a = 9
    n = 2
    x = 3
    while a > (d := x // a**(n-1)):
        a = ((n-1)*a + d) // n
    check("a", a, 1)


def test_named_expression_assignment_15() -> None:
    while a := False:
        assert False, "While body executed"
    check("a", a, False)


def test_named_expression_assignment_16() -> None:
    a, b = 1, 2
    fib = {(c := a): (a := b) + (b := a + c) - b for __ in range(6)}
    check("fib", fib, {1: 2, 2: 3, 3: 5, 5: 8, 8: 13, 13: 21})


def test_named_expression_assignment_17() -> None:
    a = [1]
    element = a[b:=0]
    check("b", b, 0)
    check("element", element, a[0])


class TwoDimensionalList:
    def __init__(self, two_dimensional_list: list[list[int]]) -> None:
        self.two_dimensional_list = two_dimensional_list

    def __getitem__(self, index: tuple[int, int]) -> int:
        return self.two_dimensional_list[index[0]][index[1]]


def test_named_expression_assignment_18() -> None:
    a = TwoDimensionalList([[1], [2]])
    element = a[b:=0, c:=0]
    check("b", b, 0)
    check("c", c, 0)
    check("element", element, a.two_dimensional_list[b][c])


def test_named_expression_scope_02() -> None:
    total = 0
    partial_sums = [total := total + v for v in range(5)]
    check("partial_sums", partial_sums, [0, 1, 3, 6, 10])
    check("total", total, 10)


def test_named_expression_scope_03() -> None:
    containsOne = any((lastNum := num) == 1 for num in [1, 2, 3])
    check("containsOne", containsOne, True)
    check("lastNum", lastNum, 1)


def test_named_expression_scope_04() -> None:
    def spam(a):
        return a
    res: list[list[int | float]] = [[y := spam(x), x/y] for x in range(1, 5)]
    check("y", y, 4)


def test_named_expression_scope_05() -> None:
    def spam(a):
        return a
    input_data = [1, 2, 3]
    res = [(x, y, x/y) for x in input_data if (y := spam(x)) > 0]
    check("res", res, [(1, 1, 1.0), (2, 2, 1.0), (3, 3, 1.0)])
    check("y", y, 3)


def test_named_expression_scope_06() -> None:
    res = [[spam := i for i in range(3)] for j in range(2)]
    check("res", res, [[0, 1, 2], [0, 1, 2]])
    check("spam", spam, 2)


def test_named_expression_scope_07() -> None:
    len(lines := [1, 2])
    check("lines", lines, [1, 2])


def test_named_expression_scope_08() -> None:
    def spam(a):
        return a

    def eggs(b):
        return b * 2

    res = [spam(a := eggs(b := h)) for h in range(2)]
    check("res", res, [0, 2])
    check("a", a, 2)
    check("b", b, 1)


def test_named_expression_scope_09() -> None:
    def spam(a):
        return a

    def eggs(b):
        return b * 2

    res = [spam(a := eggs(a := h)) for h in range(2)]
    check("res", res, [0, 2])
    check("a", a, 2)


def test_named_expression_scope_10() -> None:
    res = [b := [a := 1 for i in range(2)] for j in range(2)]
    check("res", res, [[1, 1], [1, 1]])
    check("a", a, 1)
    check("b", b, [1, 1])


def test_named_expression_scope_11() -> None:
    res = [j := i for i in range(5)]
    check("res", res, [0, 1, 2, 3, 4])
    check("j", j, 4)


def test_named_expression_scope_17() -> None:
    b = 0
    res = [b := i + b for i in range(5)]
    check("res", res, [0, 1, 3, 6, 10])
    check("b", b, 10)


def test_named_expression_scope_18() -> None:
    def spam(a):
        return a
    res = spam(b := 2)
    check("res", res, 2)
    check("b", b, 2)


def test_named_expression_scope_19() -> None:
    def spam(a):
        return a
    res = spam((b := 2))
    check("res", res, 2)
    check("b", b, 2)


def test_named_expression_scope_20() -> None:
    def spam(a):
        return a
    res = spam(a=(b := 2))
    check("res", res, 2)
    check("b", b, 2)


def test_named_expression_scope_21() -> None:
    def spam(a, b):
        return a + b
    res = spam(c := 2, b=1)
    check("res", res, 3)
    check("c", c, 2)


def test_named_expression_scope_22() -> None:
    def spam(a, b):
        return a + b
    res = spam((c := 2), b=1)
    check("res", res, 3)
    check("c", c, 2)


def test_named_expression_scope_23() -> None:
    def spam(a, b):
        return a + b
    res = spam(b=(c := 2), a=1)
    check("res", res, 3)
    check("c", c, 2)


def test_named_expression_scope_24() -> None:
    a = 10
    def spam() -> None:
        nonlocal a
        (a := 20)
    spam()
    check("a", a, 20)


a = 10


def spam() -> None:
    global a
    (a := 20)


def test_named_expression_scope_25() -> None:
    spam()
    check("a", a, 20)


# test_named_expression_variable_reuse_in_comprehensions at module scope ("Rebind global",
# "Filter global", "Body global" and "Nested global"; upstream exec()s each at module scope)
x = 1
result = [x := i for i in range(3) if (x := i) or not x]
check("rebinding x", x, 2)
check("rebinding result", result, [0, 1, 2])
x = 1
result = [x := i for i in range(3) if x or not x]
check("filter x", x, 2)
check("filter result", result, [0, 1, 2])
x = 1
result = [x for i in range(3) if (x := i) or not x]
check("body x", x, 2)
check("body result", result, [0, 1, 2])
x = 1
result = [j for i in range(3) if x or not x for j in range(3) if (x := i)][:-3]
check("nested x", x, 2)
check("nested result", result, [0, 1, 2])


def reuse_rebind_nonlocal() -> None:
    result, x = (lambda x=1: ([x := i for i in range(3) if (x := i) or not x], x))()
    check("rebinding x", x, 2)
    check("rebinding result", result, [0, 1, 2])


def reuse_filter_nonlocal() -> None:
    result, x = (lambda x=1: ([x := i for i in range(3) if x or not x], x))()
    check("filter x", x, 2)
    check("filter result", result, [0, 1, 2])


def reuse_body_nonlocal() -> None:
    result, x = (lambda x=1: ([x for i in range(3) if (x := i) or not x], x))()
    check("body x", x, 2)
    check("body result", result, [0, 1, 2])


def reuse_nested_nonlocal() -> None:
    result, x = (lambda x=1: ([j for i in range(3) if x or not x for j in range(3) if (x := i)][:-3], x))()
    check("nested x", x, 2)
    check("nested result", result, [0, 1, 2])


class Sentinel:
    pass


sentinel = Sentinel()
GLOBAL_VAR: Sentinel | None = None


def test_named_expression_global_scope() -> None:
    global GLOBAL_VAR
    def f() -> None:
        global GLOBAL_VAR
        [GLOBAL_VAR := sentinel for _ in range(1)]
        check("GLOBAL_VAR in f", GLOBAL_VAR is sentinel, True)
    try:
        f()
        check("GLOBAL_VAR", GLOBAL_VAR is sentinel, True)
    finally:
        GLOBAL_VAR = None


def test_named_expression_global_scope_no_global_keyword() -> None:
    def f() -> None:
        GLOBAL_VAR: Sentinel | None = None
        [GLOBAL_VAR := sentinel for _ in range(1)]
        check("GLOBAL_VAR in f", GLOBAL_VAR is sentinel, True)
    f()
    check("GLOBAL_VAR", GLOBAL_VAR is None, True)


def test_named_expression_nonlocal_scope() -> None:
    sentinel = Sentinel()
    def f() -> None:
        nonlocal_var: Sentinel | None = None
        def g() -> None:
            nonlocal nonlocal_var
            [nonlocal_var := sentinel for _ in range(1)]
        g()
        check("nonlocal_var", nonlocal_var is sentinel, True)
    f()


def test_named_expression_nonlocal_scope_no_nonlocal_keyword() -> None:
    sentinel = Sentinel()
    def f() -> None:
        nonlocal_var: Sentinel | None = None
        def g() -> None:
            [nonlocal_var := sentinel for _ in range(1)]
        g()
        check("nonlocal_var", nonlocal_var is None, True)
    f()


test_named_expression_assignment_01()
test_named_expression_assignment_02()
test_named_expression_assignment_03()
test_named_expression_assignment_04()
test_named_expression_assignment_05()
test_named_expression_assignment_06()
test_named_expression_assignment_07()
test_named_expression_assignment_08()
test_named_expression_assignment_09()
test_named_expression_assignment_10()
test_named_expression_assignment_11()
test_named_expression_assignment_12()
test_named_expression_assignment_13()
test_named_expression_assignment_14()
test_named_expression_assignment_15()
test_named_expression_assignment_16()
test_named_expression_assignment_17()
test_named_expression_assignment_18()
test_named_expression_scope_02()
test_named_expression_scope_03()
test_named_expression_scope_04()
test_named_expression_scope_05()
test_named_expression_scope_06()
test_named_expression_scope_07()
test_named_expression_scope_08()
test_named_expression_scope_09()
test_named_expression_scope_10()
test_named_expression_scope_11()
test_named_expression_scope_17()
test_named_expression_scope_18()
test_named_expression_scope_19()
test_named_expression_scope_20()
test_named_expression_scope_21()
test_named_expression_scope_22()
test_named_expression_scope_23()
test_named_expression_scope_24()
test_named_expression_scope_25()
reuse_rebind_nonlocal()
reuse_filter_nonlocal()
reuse_body_nonlocal()
reuse_nested_nonlocal()
test_named_expression_global_scope()
test_named_expression_global_scope_no_global_keyword()
test_named_expression_nonlocal_scope()
test_named_expression_nonlocal_scope_no_nonlocal_keyword()
