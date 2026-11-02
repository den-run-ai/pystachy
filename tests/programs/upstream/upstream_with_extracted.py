# CPython 3.13.16 Lib/test/test_with.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 dbcf093c3ed4e5be77fd6f345c178d545b7cd741f73dcac2a55cf97596e84b7f),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: AssignmentTargetTestCase.testWithExtendedTargets.
"""Unit tests for the with statement specified in PEP 343."""
from contextlib import _GeneratorContextManager, contextmanager, nullcontext

class AssignmentTargetTestCase:

    def testWithExtendedTargets(self):
        with nullcontext(range(1, 5)) as (a, *b, c):
            assert a == 1
            assert b == [2, 3]
            assert c == 4


def _AssignmentTargetTestCase__testWithExtendedTargets():
    t = AssignmentTargetTestCase()
    t.testWithExtendedTargets()
    print('ok AssignmentTargetTestCase.testWithExtendedTargets')


_AssignmentTargetTestCase__testWithExtendedTargets()
