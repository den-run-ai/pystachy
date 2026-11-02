# CPython 3.13.16 Lib/test/test_opcodes.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 2c30b2eeffad6d2b8eefa0bea40b7a7ce1e3674c5b6912805d81f1b3455d9c11),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: OpcodeTest.test_try_inside_for_loop.
class OpcodeTest:

    def test_try_inside_for_loop(self):
        n = 0
        for i in range(10):
            n = n + i
            try:
                1 / 0
            except NameError:
                pass
            except ZeroDivisionError:
                pass
            except TypeError:
                pass
            try:
                pass
            except:
                pass
            try:
                pass
            finally:
                pass
            n = n + i
        if n != 90:
            raise AssertionError('try inside for')


def _OpcodeTest__test_try_inside_for_loop():
    t = OpcodeTest()
    t.test_try_inside_for_loop()
    print('ok OpcodeTest.test_try_inside_for_loop')


_OpcodeTest__test_try_inside_for_loop()
