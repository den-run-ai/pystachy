# CPython 3.13.16 Lib/test/test_augassign.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 fa336b354cb98b5e290f71d9565cc0c1fc26d603450c9b96a2ee2a927ff99ea6),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: AugAssignTest.testBasic, AugAssignTest.testSequences.
class AugAssignTest:

    def testBasic(self):
        x = 2
        x += 1
        x *= 2
        x **= 2
        x -= 8
        x //= 5
        x %= 3
        x &= 2
        x |= 5
        x ^= 1
        x /= 2
        assert x == 3.0

    def testSequences(self):
        x = [1, 2]
        x += [3, 4]
        x *= 2
        assert x == [1, 2, 3, 4, 1, 2, 3, 4]
        x = [1, 2, 3]
        y = x
        x[1:2] *= 2
        y[1:2] += [1]
        assert x == [1, 2, 1, 2, 3]
        assert x is y


def _AugAssignTest__testBasic():
    t = AugAssignTest()
    t.testBasic()
    print('ok AugAssignTest.testBasic')


def _AugAssignTest__testSequences():
    t = AugAssignTest()
    t.testSequences()
    print('ok AugAssignTest.testSequences')


_AugAssignTest__testBasic()
_AugAssignTest__testSequences()
