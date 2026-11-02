# CPython 3.13.16 Lib/test/test_unicodedata.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 0c2dda3daca931131fecc7241215f5eb484a705ad7bcc2aab110c2d838cf95ad),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: NormalizationTest.test_bug_834676.
""" Tests for the unicodedata module.

    Written by Marc-Andre Lemburg (mal@lemburg.com).

    (c) Copyright CNRI, All Rights Reserved. NO WARRANTY.

"""
from functools import partial
import sys
import unicodedata

def iterallchars():
    maxunicode = 65535 if quicktest else sys.maxunicode
    return map(chr, range(maxunicode + 1))

class NormalizationTest:

    @staticmethod
    def check_version(testfile):
        hdr = testfile.readline()
        return unicodedata.unidata_version in hdr

    @staticmethod
    def unistr(data):
        data = [int(x, 16) for x in data.split(' ')]
        return ''.join([chr(x) for x in data])

    def run_normalization_tests(self, testdata, ucd):
        part = None
        part1_data = set()
        NFC = partial(ucd.normalize, 'NFC')
        NFKC = partial(ucd.normalize, 'NFKC')
        NFD = partial(ucd.normalize, 'NFD')
        NFKD = partial(ucd.normalize, 'NFKD')
        is_normalized = ucd.is_normalized
        for line in testdata:
            if '#' in line:
                line = line.split('#')[0]
            line = line.strip()
            if not line:
                continue
            if line.startswith('@Part'):
                part = line.split()[0]
                continue
            c1, c2, c3, c4, c5 = [self.unistr(x) for x in line.split(';')[:-1]]
            assert c2 == NFC(c1) == NFC(c2) == NFC(c3)
            assert c4 == NFC(c4) == NFC(c5)
            assert c3 == NFD(c1) == NFD(c2) == NFD(c3)
            assert c5 == NFD(c4) == NFD(c5)
            assert c4 == NFKC(c1) == NFKC(c2) == NFKC(c3) == NFKC(c4) == NFKC(c5)
            assert c5 == NFKD(c1) == NFKD(c2) == NFKD(c3) == NFKD(c4) == NFKD(c5)
            assert is_normalized('NFC', c2)
            assert is_normalized('NFC', c4)
            assert is_normalized('NFD', c3)
            assert is_normalized('NFD', c5)
            assert is_normalized('NFKC', c4)
            assert is_normalized('NFKD', c5)
            if part == '@Part1':
                part1_data.add(c1)
        for X in iterallchars():
            if X in part1_data:
                continue
            assert X == NFC(X) == NFD(X) == NFKC(X) == NFKD(X)

    def test_bug_834676(self):
        unicodedata.normalize('NFC', '한글')


def _NormalizationTest__test_bug_834676():
    t = NormalizationTest()
    t.test_bug_834676()
    print('ok NormalizationTest.test_bug_834676')


_NormalizationTest__test_bug_834676()
