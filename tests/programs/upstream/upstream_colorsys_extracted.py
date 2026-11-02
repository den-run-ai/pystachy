# CPython 3.13.16 Lib/test/test_colorsys.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 f48dd64aaf7497c5f5809803345581f1daac03d5a5ed148a661066d0200d7661),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: ColorsysTest.test_hls_roundtrip, ColorsysTest.test_hls_values,
#   ColorsysTest.test_hsv_roundtrip, ColorsysTest.test_hsv_values,
#   ColorsysTest.test_yiq_roundtrip, ColorsysTest.test_yiq_to_rgb_clamping,
#   ColorsysTest.test_yiq_values.
import colorsys

def frange(start, stop, step):
    while start <= stop:
        yield start
        start += step

class ColorsysTest:

    def assertTripleEqual(self, tr1, tr2):
        assert len(tr1) == 3
        assert len(tr2) == 3
        assert tr1[0] == tr2[0] or round(abs(tr2[0] - tr1[0]), 7) == 0
        assert tr1[1] == tr2[1] or round(abs(tr2[1] - tr1[1]), 7) == 0
        assert tr1[2] == tr2[2] or round(abs(tr2[2] - tr1[2]), 7) == 0

    def test_hsv_roundtrip(self):
        for r in frange(0.0, 1.0, 0.2):
            for g in frange(0.0, 1.0, 0.2):
                for b in frange(0.0, 1.0, 0.2):
                    rgb = (r, g, b)
                    self.assertTripleEqual(rgb, colorsys.hsv_to_rgb(*colorsys.rgb_to_hsv(*rgb)))

    def test_hsv_values(self):
        values = [((0.0, 0.0, 0.0), (0, 0.0, 0.0)), ((0.0, 0.0, 1.0), (4.0 / 6.0, 1.0, 1.0)), ((0.0, 1.0, 0.0), (2.0 / 6.0, 1.0, 1.0)), ((0.0, 1.0, 1.0), (3.0 / 6.0, 1.0, 1.0)), ((1.0, 0.0, 0.0), (0, 1.0, 1.0)), ((1.0, 0.0, 1.0), (5.0 / 6.0, 1.0, 1.0)), ((1.0, 1.0, 0.0), (1.0 / 6.0, 1.0, 1.0)), ((1.0, 1.0, 1.0), (0, 0.0, 1.0)), ((0.5, 0.5, 0.5), (0, 0.0, 0.5))]
        for rgb, hsv in values:
            self.assertTripleEqual(hsv, colorsys.rgb_to_hsv(*rgb))
            self.assertTripleEqual(rgb, colorsys.hsv_to_rgb(*hsv))
            h, s, v = hsv
            self.assertTripleEqual(rgb, colorsys.hsv_to_rgb(h + 1.0, s, v))

    def test_hls_roundtrip(self):
        for r in frange(0.0, 1.0, 0.2):
            for g in frange(0.0, 1.0, 0.2):
                for b in frange(0.0, 1.0, 0.2):
                    rgb = (r, g, b)
                    self.assertTripleEqual(rgb, colorsys.hls_to_rgb(*colorsys.rgb_to_hls(*rgb)))

    def test_hls_values(self):
        values = [((0.0, 0.0, 0.0), (0, 0.0, 0.0)), ((0.0, 0.0, 1.0), (4.0 / 6.0, 0.5, 1.0)), ((0.0, 1.0, 0.0), (2.0 / 6.0, 0.5, 1.0)), ((0.0, 1.0, 1.0), (3.0 / 6.0, 0.5, 1.0)), ((1.0, 0.0, 0.0), (0, 0.5, 1.0)), ((1.0, 0.0, 1.0), (5.0 / 6.0, 0.5, 1.0)), ((1.0, 1.0, 0.0), (1.0 / 6.0, 0.5, 1.0)), ((1.0, 1.0, 1.0), (0, 1.0, 0.0)), ((0.5, 0.5, 0.5), (0, 0.5, 0.0))]
        for rgb, hls in values:
            self.assertTripleEqual(hls, colorsys.rgb_to_hls(*rgb))
            self.assertTripleEqual(rgb, colorsys.hls_to_rgb(*hls))

    def test_yiq_roundtrip(self):
        for r in frange(0.0, 1.0, 0.2):
            for g in frange(0.0, 1.0, 0.2):
                for b in frange(0.0, 1.0, 0.2):
                    rgb = (r, g, b)
                    self.assertTripleEqual(rgb, colorsys.yiq_to_rgb(*colorsys.rgb_to_yiq(*rgb)))

    def test_yiq_to_rgb_clamping(self):
        values = [((1.0, 0.0, 1.0), (0.0, 0.5, 1.0)), ((0.0, 1.0, 0.0), (0.25, -1.0, -1.0)), ((0.0, 0.0, 1.0), (0.0, -1.0, 0.5))]
        for rgb, yiq in values:
            self.assertTripleEqual(rgb, colorsys.yiq_to_rgb(*yiq))

    def test_yiq_values(self):
        values = [((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)), ((0.0, 0.0, 1.0), (0.11, -0.3217, 0.3121)), ((0.0, 1.0, 0.0), (0.59, -0.2773, -0.5251)), ((0.0, 1.0, 1.0), (0.7, -0.599, -0.213)), ((1.0, 0.0, 0.0), (0.3, 0.599, 0.213)), ((1.0, 0.0, 1.0), (0.41, 0.2773, 0.5251)), ((1.0, 1.0, 0.0), (0.89, 0.3217, -0.3121)), ((1.0, 1.0, 1.0), (1.0, 0.0, 0.0)), ((0.5, 0.5, 0.5), (0.5, 0.0, 0.0))]
        for rgb, yiq in values:
            self.assertTripleEqual(yiq, colorsys.rgb_to_yiq(*rgb))
            self.assertTripleEqual(rgb, colorsys.yiq_to_rgb(*yiq))


def _ColorsysTest__test_hls_roundtrip():
    t = ColorsysTest()
    t.test_hls_roundtrip()
    print('ok ColorsysTest.test_hls_roundtrip')


def _ColorsysTest__test_hls_values():
    t = ColorsysTest()
    t.test_hls_values()
    print('ok ColorsysTest.test_hls_values')


def _ColorsysTest__test_hsv_roundtrip():
    t = ColorsysTest()
    t.test_hsv_roundtrip()
    print('ok ColorsysTest.test_hsv_roundtrip')


def _ColorsysTest__test_hsv_values():
    t = ColorsysTest()
    t.test_hsv_values()
    print('ok ColorsysTest.test_hsv_values')


def _ColorsysTest__test_yiq_roundtrip():
    t = ColorsysTest()
    t.test_yiq_roundtrip()
    print('ok ColorsysTest.test_yiq_roundtrip')


def _ColorsysTest__test_yiq_to_rgb_clamping():
    t = ColorsysTest()
    t.test_yiq_to_rgb_clamping()
    print('ok ColorsysTest.test_yiq_to_rgb_clamping')


def _ColorsysTest__test_yiq_values():
    t = ColorsysTest()
    t.test_yiq_values()
    print('ok ColorsysTest.test_yiq_values')


_ColorsysTest__test_hls_roundtrip()
_ColorsysTest__test_hls_values()
_ColorsysTest__test_hsv_roundtrip()
_ColorsysTest__test_hsv_values()
_ColorsysTest__test_yiq_roundtrip()
_ColorsysTest__test_yiq_to_rgb_clamping()
_ColorsysTest__test_yiq_values()
