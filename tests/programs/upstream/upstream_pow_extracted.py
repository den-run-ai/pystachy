# CPython 3.13.16 Lib/test/test_pow.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 0cfbf5bc3b271db92d5f728c649b9501b4c786d42db74bc75afeb41a54dde27d),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: PowTest.test_negative_exponent, PowTest.test_other.
import math

class PowTest:

    def powtest(self, type):
        if type != float:
            for i in range(-1000, 1000):
                assert pow(type(i), 0) == 1
                assert pow(type(i), 1) == type(i)
                assert pow(type(0), 1) == type(0)
                assert pow(type(1), 1) == type(1)
            for i in range(-100, 100):
                assert pow(type(i), 3) == i * i * i
            pow2 = 1
            for i in range(0, 31):
                assert pow(2, i) == pow2
                if i != 30:
                    pow2 = pow2 * 2
            for i in list(range(-10, 0)) + list(range(1, 10)):
                ii = type(i)
                inv = pow(ii, -1)
                for jj in range(-10, 0):
                    assert pow(ii, jj) == pow(inv, -jj) or round(abs(pow(inv, -jj) - pow(ii, jj)), 7) == 0
        for othertype in (int, float):
            for i in range(1, 100):
                zero = type(0)
                exp = -othertype(i / 10.0)
                if exp == 0:
                    continue
                try:
                    pow(zero, exp)
                except ZeroDivisionError:
                    pass
                else:
                    raise AssertionError('did not raise')
        il, ih = (-20, 20)
        jl, jh = (-5, 5)
        kl, kh = (-10, 10)
        asseq = self.assertEqual
        if type == float:
            il = 1
            asseq = self.assertAlmostEqual
        elif type == int:
            jl = 0
        elif type == int:
            jl, jh = (0, 15)
        for i in range(il, ih + 1):
            for j in range(jl, jh + 1):
                for k in range(kl, kh + 1):
                    if k != 0:
                        if type == float or j < 0:
                            try:
                                pow(type(i), j, k)
                            except TypeError:
                                pass
                            else:
                                raise AssertionError('did not raise')
                            continue
                        asseq(pow(type(i), j, k), pow(type(i), j) % type(k))

    def test_other(self):
        assert pow(3, 3) % 8 == pow(3, 3, 8)
        assert pow(3, 3) % -8 == pow(3, 3, -8)
        assert pow(3, 2) % -2 == pow(3, 2, -2)
        assert pow(-3, 3) % 8 == pow(-3, 3, 8)
        assert pow(-3, 3) % -8 == pow(-3, 3, -8)
        assert pow(5, 2) % -8 == pow(5, 2, -8)
        assert pow(3, 3) % 8 == pow(3, 3, 8)
        assert pow(3, 3) % -8 == pow(3, 3, -8)
        assert pow(3, 2) % -2 == pow(3, 2, -2)
        assert pow(-3, 3) % 8 == pow(-3, 3, 8)
        assert pow(-3, 3) % -8 == pow(-3, 3, -8)
        assert pow(5, 2) % -8 == pow(5, 2, -8)
        for i in range(-10, 11):
            for j in range(0, 6):
                for k in range(-7, 11):
                    if j >= 0 and k != 0:
                        assert pow(i, j) % k == pow(i, j, k)
                    if j >= 0 and k != 0:
                        assert pow(int(i), j) % k == pow(int(i), j, k)

    def test_negative_exponent(self):
        for a in range(-50, 50):
            for m in range(-50, 50):
                if m != 0 and math.gcd(a, m) == 1:
                    inv = pow(a, -1, m)
                    assert inv == inv % m
                    assert (inv * a - 1) % m == 0
                    assert pow(a, -2, m) == pow(inv, 2, m)
                    assert pow(a, -3, m) == pow(inv, 3, m)
                    assert pow(a, -1001, m) == pow(inv, 1001, m)
                else:
                    try:
                        pow(a, -1, m)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError('did not raise')
                    try:
                        pow(a, -2, m)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError('did not raise')
                    try:
                        pow(a, -1001, m)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError('did not raise')


def _PowTest__test_negative_exponent():
    t = PowTest()
    t.test_negative_exponent()
    print('ok PowTest.test_negative_exponent')


def _PowTest__test_other():
    t = PowTest()
    t.test_other()
    print('ok PowTest.test_other')


_PowTest__test_negative_exponent()
_PowTest__test_other()
