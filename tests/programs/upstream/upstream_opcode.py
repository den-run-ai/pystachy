# Adapted from CPython 3.13.16 Lib/test/test__opcode.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91 (SHA-256
# 26d8f889040bbd9416970111df4e784a7f1047901428f9e1758bfa6b96c23a60): every test of its classes
# OpListTests (test_invalid_opcodes, test_is_valid, test_oplists), StackEffectTests
# (test_stack_effect, test_stack_effect_jump) and SpecializationStatsTests
# (test_specialization_stats), with lib/'s _opcode stand-in and opcode module.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function named after its class and method; assertEqual(a, b) asserts
# a == b, assertIn(x, xs) asserts x in xs, assertRaises(E, f, ...) is a try statement, and a
# subTest() loop asserts without printing. The test reads dis's names from opcode, which dis
# re-exports them from (dis itself does not compile: dis.py:27 reads types.MethodType), and builds
# dis.deoptmap from opcode._specializations as dis.py builds it. check_bool_function_result() and
# check_function() take an opcode predicate as a value, as upstream; the ops of the first are ints,
# as every caller's are (its branch for an opcode's name is left out). filter() of a lambda over
# dis.opmap.items() is a loop that skips those items.
# EXCLUDED upstream cases:
# - assertIsInstance(func(op), bool): the predicates' return type is bool as the program compiles
# - test_specialization_stats' checks of the dict that get_specialization_stats() gives in a CPython
#   built with Py_STATS: it gives None here, as in the default build of CPython, where upstream
#   skips them too
import opcode
import _opcode
from _opcode import stack_effect
from typing import Callable

opmap = opcode.opmap
deoptmap = {specialized: base for base, family in opcode._specializations.items() for specialized in family}


def check_bool_function_result(func: Callable[[int], bool], ops: list[int], expected: bool) -> None:
    for op in ops:
        assert func(op) == expected, op


def OpListTests_test_invalid_opcodes() -> None:
    invalid = [-100, -1, 255, 512, 513, 1000]
    check_bool_function_result(_opcode.is_valid, invalid, False)
    check_bool_function_result(_opcode.has_arg, invalid, False)
    check_bool_function_result(_opcode.has_const, invalid, False)
    check_bool_function_result(_opcode.has_name, invalid, False)
    check_bool_function_result(_opcode.has_jump, invalid, False)
    check_bool_function_result(_opcode.has_free, invalid, False)
    check_bool_function_result(_opcode.has_local, invalid, False)
    check_bool_function_result(_opcode.has_exc, invalid, False)
    print("test_invalid_opcodes ok")


def OpListTests_test_is_valid() -> None:
    names = [
        'CACHE',
        'POP_TOP',
        'IMPORT_NAME',
        'JUMP',
        'INSTRUMENTED_RETURN_VALUE',
    ]
    opcodes = [opmap[opname] for opname in names]
    check_bool_function_result(_opcode.is_valid, opcodes, True)
    print("test_is_valid ok")


def check_function(func: Callable[[int], bool], expected: list[int]) -> None:
    for op in [-10, 520]:
        res = func(op)
        assert res == (op in expected), op


def OpListTests_test_oplists() -> None:
    check_function(_opcode.has_arg, opcode.hasarg)
    check_function(_opcode.has_const, opcode.hasconst)
    check_function(_opcode.has_name, opcode.hasname)
    check_function(_opcode.has_jump, opcode.hasjump)
    check_function(_opcode.has_free, opcode.hasfree)
    check_function(_opcode.has_local, opcode.haslocal)
    check_function(_opcode.has_exc, opcode.hasexc)
    print("test_oplists ok")


def StackEffectTests_test_stack_effect() -> None:
    assert stack_effect(opmap['POP_TOP']) == -1
    assert stack_effect(opmap['BUILD_SLICE'], 0) == -1
    assert stack_effect(opmap['BUILD_SLICE'], 1) == -1
    assert stack_effect(opmap['BUILD_SLICE'], 3) == -2
    try:
        stack_effect(30000)
        raise AssertionError("ValueError not raised")
    except ValueError as e:
        print("ValueError:", e)
    # All defined opcodes
    n = 0
    for name, code in opmap.items():
        if name in deoptmap:
            continue
        if code >= opcode.MIN_INSTRUMENTED_OPCODE:
            continue
        stack_effect(code)
        stack_effect(code, 0)
        n += 1
    # All not defined opcodes
    undefined = 0
    for code in set(range(256)) - set(opmap.values()):
        try:
            stack_effect(code)
            raise AssertionError(f"ValueError not raised for {code}")
        except ValueError:
            pass
        try:
            stack_effect(code, 0)
            raise AssertionError(f"ValueError not raised for {code}, 0")
        except ValueError:
            pass
        undefined += 1
    print("test_stack_effect ok:", n, "defined,", undefined, "not defined")


def StackEffectTests_test_stack_effect_jump() -> None:
    FOR_ITER = opmap['FOR_ITER']
    assert stack_effect(FOR_ITER, 0) == 1
    assert stack_effect(FOR_ITER, 0, jump=True) == 1
    assert stack_effect(FOR_ITER, 0, jump=False) == 1
    JUMP_FORWARD = opmap['JUMP_FORWARD']
    assert stack_effect(JUMP_FORWARD, 0) == 0
    assert stack_effect(JUMP_FORWARD, 0, jump=True) == 0
    assert stack_effect(JUMP_FORWARD, 0, jump=False) == 0
    # All defined opcodes
    has_arg = opcode.hasarg
    has_exc = opcode.hasexc
    has_jump = opcode.hasjabs + opcode.hasjrel
    n = 0
    for name, code in opmap.items():
        if name in deoptmap:
            continue
        if code >= opcode.MIN_INSTRUMENTED_OPCODE:
            continue
        if code not in has_arg:
            common = stack_effect(code)
            jump = stack_effect(code, jump=True)
            nojump = stack_effect(code, jump=False)
        else:
            common = stack_effect(code, 0)
            jump = stack_effect(code, 0, jump=True)
            nojump = stack_effect(code, 0, jump=False)
        if code in has_jump or code in has_exc:
            assert common == max(jump, nojump), name
        else:
            assert jump == common, name
            assert nojump == common, name
        n += 1
    print("test_stack_effect_jump ok:", n)


def SpecializationStatsTests_test_specialization_stats() -> None:
    specialized_opcodes = [
        op.lower()
        for op in opcode._specializations
        if opcode._inline_cache_entries.get(op, 0)
    ]
    assert 'load_attr' in specialized_opcodes
    assert 'binary_subscr' in specialized_opcodes

    stats = _opcode.get_specialization_stats()
    print("test_specialization_stats ok:", sorted(specialized_opcodes), stats)


OpListTests_test_invalid_opcodes()
OpListTests_test_is_valid()
OpListTests_test_oplists()
StackEffectTests_test_stack_effect()
StackEffectTests_test_stack_effect_jump()
SpecializationStatsTests_test_specialization_stats()
