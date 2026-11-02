# CPython 3.13.16 Lib/test/test_bytes.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 aae9cf5348faa9b39bdccb13489e14facb6cdf51bfa5310a75518608645f6e06),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: BytesTest.test_compare, BytesTest.test_from_int, BytesTest.test_from_list,
#   BytesTest.test_from_ssize, BytesTest.test_from_tuple, BytesTest.test_getslice,
#   BytesTest.test_hex_separator_five_bytes, BytesTest.test_hex_separator_six_bytes,
#   BytesTest.test_none_arguments, BytesTest.test_partition, BytesTest.test_repeat_1char,
#   BytesTest.test_replace, BytesTest.test_reversed, BytesTest.test_rpartition,
#   BytesTest.test_rsplit_unicodewhitespace, BytesTest.test_split_unicodewhitespace,
#   AssortedBytesTest.test_compare_bytes_to_bytearray.
"""Unit tests for the bytes and bytearray types.

XXX This is a mess.  Common tests should be unified with string_tests.py (and
the latter should be modernized).
"""
import sys

class BaseBytesTest:

    def assertTypedEqual(self, actual, expected):
        assert type(actual) is type(expected)
        assert actual == expected

    def test_from_tuple(self):
        b = self.type2test(tuple(range(256)))
        assert len(b) == 256
        assert list(b) == list(range(256))
        b = self.type2test((1, 2, 3))
        assert b == b'\x01\x02\x03'

    def test_from_list(self):
        b = self.type2test(list(range(256)))
        assert len(b) == 256
        assert list(b) == list(range(256))
        b = self.type2test([1, 2, 3])
        assert b == b'\x01\x02\x03'

    def test_from_ssize(self):
        assert self.type2test(0) == b''
        assert self.type2test(1) == b'\x00'
        assert self.type2test(5) == b'\x00\x00\x00\x00\x00'
        try:
            self.type2test(-1)
        except ValueError:
            pass
        else:
            raise AssertionError('did not raise')
        assert self.type2test('0', 'ascii') == b'0'
        assert self.type2test(b'0') == b'0'
        try:
            self.type2test(sys.maxsize + 1)
        except OverflowError:
            pass
        else:
            raise AssertionError('did not raise')

    def test_compare(self):
        b1 = self.type2test([1, 2, 3])
        b2 = self.type2test([1, 2, 3])
        b3 = self.type2test([1, 3])
        assert b1 == b2
        assert b2 != b3
        assert b1 <= b2
        assert b1 <= b3
        assert b1 < b3
        assert b1 >= b2
        assert b3 >= b2
        assert b3 > b2
        assert not b1 != b2
        assert not b2 == b3
        assert not b1 > b2
        assert not b1 > b3
        assert not b1 >= b3
        assert not b1 < b2
        assert not b3 < b2
        assert not b3 <= b2

    def test_reversed(self):
        input = list(map(ord, 'Hello'))
        b = self.type2test(input)
        output = list(reversed(b))
        input.reverse()
        assert output == input

    def test_getslice(self):

        def by(s):
            return self.type2test(map(ord, s))
        b = by('Hello, world')
        assert b[:5] == by('Hello')
        assert b[1:5] == by('ello')
        assert b[5:7] == by(', ')
        assert b[7:] == by('world')
        assert b[7:12] == by('world')
        assert b[7:100] == by('world')
        assert b[:-7] == by('Hello')
        assert b[-11:-7] == by('ello')
        assert b[-7:-5] == by(', ')
        assert b[-5:] == by('world')
        assert b[-5:12] == by('world')
        assert b[-5:100] == by('world')
        assert b[-100:5] == by('Hello')

    def test_from_int(self):
        b = self.type2test(0)
        assert b == self.type2test()
        b = self.type2test(10)
        assert b == self.type2test([0] * 10)
        b = self.type2test(10000)
        assert b == self.type2test([0] * 10000)

    def test_repeat_1char(self):
        assert self.type2test(b'x') * 100 == self.type2test([ord('x')] * 100)

    def test_hex_separator_five_bytes(self):
        five_bytes = self.type2test(range(90, 95))
        assert five_bytes.hex() == '5a5b5c5d5e'

    def test_hex_separator_six_bytes(self):
        six_bytes = self.type2test((x * 3 for x in range(1, 7)))
        assert six_bytes.hex() == '0306090c0f12'
        assert six_bytes.hex('.', 1) == '03.06.09.0c.0f.12'
        assert six_bytes.hex(' ', 2) == '0306 090c 0f12'
        assert six_bytes.hex('-', 3) == '030609-0c0f12'
        assert six_bytes.hex(':', 4) == '0306:090c0f12'
        assert six_bytes.hex(':', 5) == '03:06090c0f12'
        assert six_bytes.hex(':', 6) == '0306090c0f12'
        assert six_bytes.hex(':', 95) == '0306090c0f12'
        assert six_bytes.hex('_', -3) == '030609_0c0f12'
        assert six_bytes.hex(':', -4) == '0306090c:0f12'
        assert six_bytes.hex(b'@', -5) == '0306090c0f@12'
        assert six_bytes.hex(':', -6) == '0306090c0f12'
        assert six_bytes.hex(' ', -95) == '0306090c0f12'

    def test_replace(self):
        b = self.type2test(b'mississippi')
        assert b.replace(b'i', b'a') == b'massassappa'
        assert b.replace(b'ss', b'x') == b'mixixippi'

    def test_split_unicodewhitespace(self):
        for b in (b'a\x1cb', b'a\x1db', b'a\x1eb', b'a\x1fb'):
            b = self.type2test(b)
            assert b.split() == [b]
        b = self.type2test(b'\t\n\x0b\x0c\r\x1c\x1d\x1e\x1f')
        assert b.split() == [b'\x1c\x1d\x1e\x1f']

    def test_rsplit_unicodewhitespace(self):
        b = self.type2test(b'\t\n\x0b\x0c\r\x1c\x1d\x1e\x1f')
        assert b.rsplit() == [b'\x1c\x1d\x1e\x1f']

    def test_partition(self):
        b = self.type2test(b'mississippi')
        assert b.partition(b'ss') == (b'mi', b'ss', b'issippi')
        assert b.partition(b'w') == (b'mississippi', b'', b'')

    def test_rpartition(self):
        b = self.type2test(b'mississippi')
        assert b.rpartition(b'ss') == (b'missi', b'ss', b'ippi')
        assert b.rpartition(b'i') == (b'mississipp', b'i', b'')
        assert b.rpartition(b'w') == (b'', b'', b'mississippi')

    def test_none_arguments(self):
        b = self.type2test(b'hello')
        l = self.type2test(b'l')
        h = self.type2test(b'h')
        x = self.type2test(b'x')
        o = self.type2test(b'o')
        assert 2 == b.find(l, None)
        assert 3 == b.find(l, -2, None)
        assert 2 == b.find(l, None, -2)
        assert 0 == b.find(h, None, None)
        assert 3 == b.rfind(l, None)
        assert 3 == b.rfind(l, -2, None)
        assert 2 == b.rfind(l, None, -2)
        assert 0 == b.rfind(h, None, None)
        assert 2 == b.index(l, None)
        assert 3 == b.index(l, -2, None)
        assert 2 == b.index(l, None, -2)
        assert 0 == b.index(h, None, None)
        assert 3 == b.rindex(l, None)
        assert 3 == b.rindex(l, -2, None)
        assert 2 == b.rindex(l, None, -2)
        assert 0 == b.rindex(h, None, None)
        assert 2 == b.count(l, None)
        assert 1 == b.count(l, -2, None)
        assert 1 == b.count(l, None, -2)
        assert 0 == b.count(x, None, None)
        assert True == b.endswith(o, None)
        assert True == b.endswith(o, -2, None)
        assert True == b.endswith(l, None, -2)
        assert False == b.endswith(x, None, None)
        assert True == b.startswith(h, None)
        assert True == b.startswith(l, -2, None)
        assert True == b.startswith(h, None, -2)
        assert False == b.startswith(x, None, None)

class BytesTest(BaseBytesTest):
    type2test = bytes

class AssortedBytesTest:

    def test_compare_bytes_to_bytearray(self):
        assert (b'abc' == bytes(b'abc')) == True
        assert (b'ab' != bytes(b'abc')) == True
        assert (b'ab' <= bytes(b'abc')) == True
        assert (b'ab' < bytes(b'abc')) == True
        assert (b'abc' >= bytes(b'ab')) == True
        assert (b'abc' > bytes(b'ab')) == True
        assert (b'abc' != bytes(b'abc')) == False
        assert (b'ab' == bytes(b'abc')) == False
        assert (b'ab' > bytes(b'abc')) == False
        assert (b'ab' >= bytes(b'abc')) == False
        assert (b'abc' < bytes(b'ab')) == False
        assert (b'abc' <= bytes(b'ab')) == False
        assert (bytes(b'abc') == b'abc') == True
        assert (bytes(b'ab') != b'abc') == True
        assert (bytes(b'ab') <= b'abc') == True
        assert (bytes(b'ab') < b'abc') == True
        assert (bytes(b'abc') >= b'ab') == True
        assert (bytes(b'abc') > b'ab') == True
        assert (bytes(b'abc') != b'abc') == False
        assert (bytes(b'ab') == b'abc') == False
        assert (bytes(b'ab') > b'abc') == False
        assert (bytes(b'ab') >= b'abc') == False
        assert (bytes(b'abc') < b'ab') == False
        assert (bytes(b'abc') <= b'ab') == False


def _BytesTest__test_compare():
    t = BytesTest()
    t.test_compare()
    print('ok BytesTest.test_compare')


def _BytesTest__test_from_int():
    t = BytesTest()
    t.test_from_int()
    print('ok BytesTest.test_from_int')


def _BytesTest__test_from_list():
    t = BytesTest()
    t.test_from_list()
    print('ok BytesTest.test_from_list')


def _BytesTest__test_from_ssize():
    t = BytesTest()
    t.test_from_ssize()
    print('ok BytesTest.test_from_ssize')


def _BytesTest__test_from_tuple():
    t = BytesTest()
    t.test_from_tuple()
    print('ok BytesTest.test_from_tuple')


def _BytesTest__test_getslice():
    t = BytesTest()
    t.test_getslice()
    print('ok BytesTest.test_getslice')


def _BytesTest__test_hex_separator_five_bytes():
    t = BytesTest()
    t.test_hex_separator_five_bytes()
    print('ok BytesTest.test_hex_separator_five_bytes')


def _BytesTest__test_hex_separator_six_bytes():
    t = BytesTest()
    t.test_hex_separator_six_bytes()
    print('ok BytesTest.test_hex_separator_six_bytes')


def _BytesTest__test_none_arguments():
    t = BytesTest()
    t.test_none_arguments()
    print('ok BytesTest.test_none_arguments')


def _BytesTest__test_partition():
    t = BytesTest()
    t.test_partition()
    print('ok BytesTest.test_partition')


def _BytesTest__test_repeat_1char():
    t = BytesTest()
    t.test_repeat_1char()
    print('ok BytesTest.test_repeat_1char')


def _BytesTest__test_replace():
    t = BytesTest()
    t.test_replace()
    print('ok BytesTest.test_replace')


def _BytesTest__test_reversed():
    t = BytesTest()
    t.test_reversed()
    print('ok BytesTest.test_reversed')


def _BytesTest__test_rpartition():
    t = BytesTest()
    t.test_rpartition()
    print('ok BytesTest.test_rpartition')


def _BytesTest__test_rsplit_unicodewhitespace():
    t = BytesTest()
    t.test_rsplit_unicodewhitespace()
    print('ok BytesTest.test_rsplit_unicodewhitespace')


def _BytesTest__test_split_unicodewhitespace():
    t = BytesTest()
    t.test_split_unicodewhitespace()
    print('ok BytesTest.test_split_unicodewhitespace')


def _AssortedBytesTest__test_compare_bytes_to_bytearray():
    t = AssortedBytesTest()
    t.test_compare_bytes_to_bytearray()
    print('ok AssortedBytesTest.test_compare_bytes_to_bytearray')


_BytesTest__test_compare()
_BytesTest__test_from_int()
_BytesTest__test_from_list()
_BytesTest__test_from_ssize()
_BytesTest__test_from_tuple()
_BytesTest__test_getslice()
_BytesTest__test_hex_separator_five_bytes()
_BytesTest__test_hex_separator_six_bytes()
_BytesTest__test_none_arguments()
_BytesTest__test_partition()
_BytesTest__test_repeat_1char()
_BytesTest__test_replace()
_BytesTest__test_reversed()
_BytesTest__test_rpartition()
_BytesTest__test_rsplit_unicodewhitespace()
_BytesTest__test_split_unicodewhitespace()
_AssortedBytesTest__test_compare_bytes_to_bytearray()
