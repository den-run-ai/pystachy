# Adapted from CPython 3.13.16 Lib/test/test_listcomps.py, its doctests (`doctests`: all but the
# generator ones) and class ListComprehensionTest: test_lambdas_with_iteration_var_as_default,
# test_free_inner_cell_outer, test_shadows_outer_cell, test_explicit_global,
# test_explicit_global_2, test_assignment_expression, test_shadow_comp_iterable_name,
# test_nested_free, test_nested, test_nested_2, test_nested_3, test_dunder_name,
# test_unbound_local_after_comprehension, test_nested_free_var_not_bound_in_outer_comp,
# test_nested_free_var_in_iter, test_nested_free_var_in_expr,
# test_assign_to_comp_iter_var_in_outer_function, test_comp_in_try_except,
# test_comp_in_try_finally, test_code_replace (without its code.replace() run) and
# test_multiple_comprehension_name_reuse; commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# The doctests print what each `>>>` line shows (doctests_frange and doctests_none are their
# frange()/lrange() and None sections). ListComprehensionTest's _check_in_scopes() runs a snippet
# at module, class and function scope and checks the names it binds: each test here is the
# snippet in a function (its function scope), checked with check(), which prints and asserts;
# a namespace that upstream passes (ns={"g": -1}) is a module global of its own name (g2, g3,
# g4), and an expected exception is caught and printed. test_multiple_comprehension_name_reuse_2
# is its second snippet; a value that is None or a list has an optional annotation.
# EXCLUDED upstream cases:
# - the class-scope runs of _check_in_scopes() (class bodies are not code here) and the module
#   ones but where noted; test_class_scope_free_var_with_class_cell, test_references_*,
#   test_super_and_class_cell_in_sibling_comps, test_in_class_scope_*,
#   test_global_in_class_scope, test_name_error_in_class_scope, test_nested_has_free_var (class
#   scope, __class__, super, locals())
# - a lambda that reads a variable of the comprehension it is in (rejected: "the lambda reads
#   'i', a variable of the comprehension it is in: not supported", #507):
#   test_lambdas_with_free_var, test_inner_cell_shadows_outer,
#   test_inner_cell_shadows_outer_no_store, test_inner_cell_shadows_outer_redefined,
#   test_explicit_global_3, test_free_var_in_comp_child, test_shadow_with_free_and_local,
#   test_nested_4, test_global_outside_cellvar_inside_plus_freevar,
#   test_cell_in_nested_comprehension, test_nested_listcomp_in_lambda
# - test_lambda_in_iter (rejected: "'a' is read before the comprehension's for clause that binds
#   it, where CPython raises UnboundLocalError (not supported)", though the lambda that reads it
#   runs only after the comprehension; see #528)
# - test_closure_can_jump_over_comp_scope (rejected: "the lambda reads 'y', which may not be
#   assigned yet where it is defined: not supported")
# - test_nameerror: reading the comprehension's variable after it is a compile-time "name 'x' is
#   not defined" here (CPython raises NameError when the code runs; documented):
#   tests/errors/upstream/upstream_listcomps_nameerror.py
# - test_cell_inner_free_outer (`x = ...`), test_unbound_local_inside_comprehension (`(l[0], l)`
#   as a target, a list holding None and a list), test_introspecting_frame_locals,
#   test_frame_locals, test_iter_var_available_in_locals, test_no_leakage_to_locals
#   (sys._getframe(), locals(), vars(), dir(), eval(), exec()), test_exception_in_post_comp_call
#   (a list of an int and None), test_code_replace_extended_arg (exec() of 300 names),
#   test_exception_locations (tracebacks), the generator doctest (grange) and the lvalue
#   SyntaxError doctests (the same errors at compile time, checked with tools/syntax_sweep.py)
def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def doctests() -> None:
    print(sum([i*i for i in range(100) if i&1 == 1]))
    print([(i,j) for i in range(3) for j in range(4)])
    print([(i,j) for i in range(4) for j in range(i)])
    print([j*j for i in range(4) for j in [i+1]])
    print([j*k for i in range(4) for j in [i+1] for k in [j+1]])
    print([j*k for i in range(4) for j, k in [(i+1, i+2)]])
    print([i*i for i in [*range(4)]])
    print([i*i for i in (*range(4),)])
    i = 20
    print(sum([i*i for i in range(100)]))
    print(i)


def frange(n: int) -> list[int]:
    return [i for i in range(n)]


def doctests_frange() -> None:
    print(frange(10))
    lrange = lambda n:  [i for i in range(n)]
    print(lrange(10))


def doctests_none() -> None:
    print([None for i in range(10)])


def test_lambdas_with_iteration_var_as_default() -> None:
    items = [(lambda i=i: i) for i in range(5)]
    y = [x() for x in items]
    check("y", y, [0, 1, 2, 3, 4])


def test_free_inner_cell_outer() -> None:
    g = 2
    def f() -> int:
        return g
    y = [g for x in [1]]
    check("y", y, [2])


g2 = -1


def test_shadows_outer_cell() -> None:
    def inner() -> int:
        return g2
    [g2 for g2 in range(5)]
    x = inner()
    check("x", x, -1)


g3 = 1


def test_explicit_global() -> None:
    global g3
    x = g3
    g3 = 2
    items = [g3 for g3 in [1]]
    y = g3
    check("x", x, 1)
    check("y", y, 2)
    check("items", items, [1])


g4 = 1


def test_explicit_global_2() -> None:
    global g4
    x = g4
    g4 = 2
    items = [g4 for x in [1]]
    y = g4
    check("x", x, 1)
    check("y", y, 2)
    check("items", items, [2])


def test_assignment_expression() -> None:
    x = -1
    items = [(x:=y) for y in range(3)]
    check("x", x, 2)


def test_shadow_comp_iterable_name() -> None:
    x = [1]
    y = [x for x in x]
    check("x", x, [1])


def test_nested_free() -> None:
    x = 1
    def g() -> int:
        [x for x in range(3)]
        return x
    g()
    check("x", x, 1)


def test_nested() -> None:
    l = [2, 3]
    y = [[x ** 2 for x in range(x)] for x in l]
    check("y", y, [[0, 1], [0, 1, 4]])


def test_nested_2() -> None:
    l = [1, 2, 3]
    x = 3
    y = [x for [x ** x for x in range(x)][x - 1] in l]
    check("y", y, [3, 3, 3])


def test_nested_3() -> None:
    l = [(1, 2), (3, 4), (5, 6)]
    y = [x for (x, [x ** x for x in range(x)][x - 1]) in l]
    check("y", y, [1, 3, 5])


def test_dunder_name() -> None:
    y = [__x for __x in [1]]
    check("y", y, [1])


def test_unbound_local_after_comprehension() -> None:
    def f() -> int:
        if False:
            x = 0
        [x for x in [1]]
        return x
    try:
        f()
    except UnboundLocalError as e:
        print(type(e).__name__, e)


def test_nested_free_var_not_bound_in_outer_comp() -> None:
    z = 1
    items = [a for a in [1] if [x for x in [1] if z]]
    check("items", items, [1])


def test_nested_free_var_in_iter() -> None:
    items = [_C for _C in [1] for [0, 1][[x for x in [1] if _C][0]] in [2]]
    check("items", items, [1])


def test_nested_free_var_in_expr() -> None:
    items = [(_C, [x for x in [1] if _C]) for _C in [0, 1]]
    expected: list[tuple[int, list[int]]] = [(0, []), (1, [1])]
    check("items", items, expected)


def test_assign_to_comp_iter_var_in_outer_function() -> None:
    a = [1 for a in [0]]
    check("a", a, [1])


def test_comp_in_try_except() -> None:
    value = ["ab"]
    result: list[int] | None = None
    snapshot: list[str] | None = None
    try:
        result = [len(value) for value in value]
    except:
        snapshot = value
        raise
    check("value", value, ["ab"])
    check("result", result, [2])
    check("snapshot", snapshot, None)
    value = ["ab"]
    result = None
    snapshot = None
    try:
        try:
            result = [int(value) for value in value]
        except:
            snapshot = value
            raise
    except ValueError as e:
        print(type(e).__name__)
    check("value", value, ["ab"])
    check("result", result, None)
    check("snapshot", snapshot, ["ab"])


def test_comp_in_try_finally() -> None:
    value = ["ab"]
    result: list[int] | None = None
    snapshot: list[str] | None = None
    try:
        result = [len(value) for value in value]
    finally:
        snapshot = value
    check("value", value, ["ab"])
    check("result", result, [2])
    check("snapshot", snapshot, ["ab"])
    value = ["ab"]
    result = None
    snapshot = None
    try:
        try:
            result = [int(value) for value in value]
        finally:
            snapshot = value
    except ValueError as e:
        print(type(e).__name__)
    check("value", value, ["ab"])
    check("result", result, None)
    check("snapshot", snapshot, ["ab"])


def test_code_replace() -> None:
    x = 3
    [x for x in (1, 2)]
    y = [x]
    check("y", y, [3])
    check("x", x, 3)


x = 3


def test_multiple_comprehension_name_reuse() -> None:
    [x for x in [1]]
    y = [x for _ in [1]]
    check("y", y, [3])


def test_multiple_comprehension_name_reuse_2() -> None:
    x = 2
    [x for x in [1]]
    y = [x for _ in [1]]
    check("x", x, 2)
    check("y", y, [2])


doctests()
doctests_frange()
doctests_none()
test_lambdas_with_iteration_var_as_default()
test_free_inner_cell_outer()
test_shadows_outer_cell()
test_explicit_global()
test_explicit_global_2()
test_assignment_expression()
test_shadow_comp_iterable_name()
test_nested_free()
test_nested()
test_nested_2()
test_nested_3()
test_dunder_name()
test_unbound_local_after_comprehension()
test_nested_free_var_not_bound_in_outer_comp()
test_nested_free_var_in_iter()
test_nested_free_var_in_expr()
test_assign_to_comp_iter_var_in_outer_function()
test_comp_in_try_except()
test_comp_in_try_finally()
test_code_replace()
test_multiple_comprehension_name_reuse()
test_multiple_comprehension_name_reuse_2()
