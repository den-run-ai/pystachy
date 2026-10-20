# Adapted from CPython 3.13.16 Lib/test/test_dictcomps.py, class DictComprehensionTest:
# test_basics, test_scope_isolation, test_scope_isolation_from_global, test_global_visibility,
# test_local_visibility, test_evaluation_order, test_assignment_idiom_in_comprehensions and
# test_star_expression, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b. Dicts of None values are annotated dict[int, None]; where upstream rebinds `expected`
# and `actual` to dicts of another value type, the second ones are expected2 and actual2;
# test_evaluation_order's add_call() and its list are annotated.
# EXCLUDED upstream cases:
# - test_illegal_assignment (compile() of SyntaxErrors: the same errors at compile time here,
#   checked with tools/syntax_sweep.py) and test_exception_locations (tracebacks)
g = "Global variable"


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def test_basics() -> None:
    expected = {0: 10, 1: 11, 2: 12, 3: 13, 4: 14, 5: 15, 6: 16, 7: 17,
                8: 18, 9: 19}
    actual = {k: k + 10 for k in range(10)}
    check("actual", actual, expected)

    expected = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9}
    actual = {k: v for k in range(10) for v in range(10) if k == v}
    check("actual", actual, expected)


def test_scope_isolation() -> None:
    k = "Local Variable"

    expected: dict[int, None] = {0: None, 1: None, 2: None, 3: None, 4: None, 5: None,
                6: None, 7: None, 8: None, 9: None}
    actual: dict[int, None] = {k: None for k in range(10)}
    check("actual", actual, expected)
    check("k", k, "Local Variable")

    expected2 = {9: 1, 18: 2, 19: 2, 27: 3, 28: 3, 29: 3, 36: 4, 37: 4,
                38: 4, 39: 4, 45: 5, 46: 5, 47: 5, 48: 5, 49: 5, 54: 6,
                55: 6, 56: 6, 57: 6, 58: 6, 59: 6, 63: 7, 64: 7, 65: 7,
                66: 7, 67: 7, 68: 7, 69: 7, 72: 8, 73: 8, 74: 8, 75: 8,
                76: 8, 77: 8, 78: 8, 79: 8, 81: 9, 82: 9, 83: 9, 84: 9,
                85: 9, 86: 9, 87: 9, 88: 9, 89: 9}
    actual2 = {k: v for v in range(10) for k in range(v * 9, v * 10)}
    check("k", k, "Local Variable")
    check("actual", actual2, expected2)


def test_scope_isolation_from_global() -> None:
    expected: dict[int, None] = {0: None, 1: None, 2: None, 3: None, 4: None, 5: None,
                6: None, 7: None, 8: None, 9: None}
    actual: dict[int, None] = {g: None for g in range(10)}
    check("actual", actual, expected)
    check("g", g, "Global variable")

    expected2 = {9: 1, 18: 2, 19: 2, 27: 3, 28: 3, 29: 3, 36: 4, 37: 4,
                38: 4, 39: 4, 45: 5, 46: 5, 47: 5, 48: 5, 49: 5, 54: 6,
                55: 6, 56: 6, 57: 6, 58: 6, 59: 6, 63: 7, 64: 7, 65: 7,
                66: 7, 67: 7, 68: 7, 69: 7, 72: 8, 73: 8, 74: 8, 75: 8,
                76: 8, 77: 8, 78: 8, 79: 8, 81: 9, 82: 9, 83: 9, 84: 9,
                85: 9, 86: 9, 87: 9, 88: 9, 89: 9}
    actual2 = {g: v for v in range(10) for g in range(v * 9, v * 10)}
    check("g", g, "Global variable")
    check("actual", actual2, expected2)


def test_global_visibility() -> None:
    expected = {0: 'Global variable', 1: 'Global variable',
                2: 'Global variable', 3: 'Global variable',
                4: 'Global variable', 5: 'Global variable',
                6: 'Global variable', 7: 'Global variable',
                8: 'Global variable', 9: 'Global variable'}
    actual = {k: g for k in range(10)}
    check("actual", actual, expected)


def test_local_visibility() -> None:
    v = "Local variable"
    expected = {0: 'Local variable', 1: 'Local variable',
                2: 'Local variable', 3: 'Local variable',
                4: 'Local variable', 5: 'Local variable',
                6: 'Local variable', 7: 'Local variable',
                8: 'Local variable', 9: 'Local variable'}
    actual = {k: v for k in range(10)}
    check("actual", actual, expected)
    check("v", v, "Local variable")


def test_evaluation_order() -> None:
    expected = {
        'H': 'W',
        'e': 'o',
        'l': 'l',
        'o': 'd',
    }

    expected_calls = [
        ('key', 'H'), ('value', 'W'),
        ('key', 'e'), ('value', 'o'),
        ('key', 'l'), ('value', 'r'),
        ('key', 'l'), ('value', 'l'),
        ('key', 'o'), ('value', 'd'),
    ]

    actual_calls: list[tuple[str, str]] = []

    def add_call(pos: str, value: str) -> str:
        actual_calls.append((pos, value))
        return value

    actual = {
        add_call('key', k): add_call('value', v)
        for k, v in zip('Hello', 'World')
    }

    check("actual", actual, expected)
    check("actual_calls", actual_calls, expected_calls)


def test_assignment_idiom_in_comprehensions() -> None:
    expected = {1: 1, 2: 4, 3: 9, 4: 16}
    actual = {j: j*j for i in range(4) for j in [i+1]}
    check("actual", actual, expected)
    expected = {3: 2, 5: 6, 7: 12, 9: 20}
    actual = {j+k: j*k for i in range(4) for j in [i+1] for k in [j+1]}
    check("actual", actual, expected)
    expected = {3: 2, 5: 6, 7: 12, 9: 20}
    actual = {j+k: j*k for i in range(4)  for j, k in [(i+1, i+2)]}
    check("actual", actual, expected)


def test_star_expression() -> None:
    expected = {0: 0, 1: 1, 2: 4, 3: 9}
    check("list", {i: i*i for i in [*range(4)]}, expected)
    check("tuple", {i: i*i for i in (*range(4),)}, expected)


test_basics()
test_scope_isolation()
test_scope_isolation_from_global()
test_global_visibility()
test_local_visibility()
test_evaluation_order()
test_assignment_idiom_in_comprehensions()
test_star_expression()
