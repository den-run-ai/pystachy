# pystachy: python-int
# Original differential cases: execute unchanged under CPython builtin int.
lo = -9223372036854775808
hi = 9223372036854775807
assert hi + 1 == 9223372036854775808
assert lo - 1 == -9223372036854775809
assert -lo == abs(lo) == 9223372036854775808
assert lo // -1 == 9223372036854775808
assert lo % -1 == 0
assert hi * hi == 85070591730234615847396907784232501249
assert (hi + 1) - 1 == hi
assert ((hi + 1) - 1) + 1 == hi + 1
assert int('9223372036854775808') == hi + 1
assert int('0xffffffffffffffffffffffffffffffff', 0) == 2 ** 128 - 1
assert 0x10000000000000000 == 2 ** 64
assert f"{0x10000000000000000}" == str(2 ** 64)
assert 0xffffffffffffffffffffffffffffffff == 2 ** 128 - 1
assert 0o2000000000000000000000000000000000000000000 == 2 ** 127
assert 0b10000000000000000000000000000000000000000000000000000000000000000 == 2 ** 64
assert isinstance(hi + 1, int) and isinstance(True, int) and isinstance(len('abc'), int)
assert not isinstance('1', int)
x = hi + 1
assert int(x) is x
print('promote, demote, literals, construction')

values = [0, 1, -1, lo, hi, hi + 1, lo - 1, 2 ** 127, -(2 ** 128), 2 ** 255 + 17]
for a in values:
    print(a, +a, -a, ~a, abs(a), a.bit_length(), a.bit_count(), hash(a))
    for b in values:
        print(a + b, a - b, a * b, a & b, a | b, a ^ b)
        if b:
            q, r = divmod(a, b)
            assert a == b * q + r
            assert (0 <= r < b) if b > 0 else (b < r <= 0)
            print(q, r)
    for count in [0, 1, 29, 30, 31, 62, 63, 64, 65, 128]:
        assert (a << count) >> count == a
        print(a << count, a >> count)
assert -7 >> (2 ** 100) == -1
assert 7 >> (2 ** 100) == 0
assert 0 << (2 ** 100) == 0
for a in [-9, 0, 3, 9223372036854775808]:
    for e in [0, 1, 2, 17]:
        print(a ** e, pow(a, e))
for modulus in [-97, -1, 1, 97, 2 ** 127 - 1]:
    for exponent in [0, 1, 37, 2 ** 64 + 1]:
        print(pow(17, exponent, modulus))
assert pow(3, -1, 11) == 4
assert pow(3, -1, -11) == -7
assert pow(3, -3, 11) == 9
print('arithmetic and modular inverse')

caught = 0
try:
    hi // 0
except ZeroDivisionError:
    caught += 1
try:
    (hi + 1) % 0
except ZeroDivisionError:
    caught += 1
try:
    1 << -1
except ValueError:
    caught += 1
try:
    0 >> -(2 ** 100)
except ValueError:
    caught += 1
try:
    pow(6, -1, 9)
except ValueError:
    caught += 1
try:
    pow(2, 3, 0)
except ValueError:
    caught += 1
try:
    int(1, 10)
except TypeError:
    caught += 1
try:
    int('1', None)
except TypeError:
    caught += 1
assert caught == 8
print('exceptions', caught)
for a in values:
    print(bin(a), oct(a), hex(a))

assert "a" * 3 == 3 * "a" == "aaa"
assert [1, 2] * 2 == 2 * [1, 2] == [1, 2, 1, 2]
text = "9" * 4300
assert str(int(text)) == text
limits = 0
try:
    int("1" + "0" * 4300)
except ValueError:
    limits += 1
try:
    str(10 ** 4300)
except ValueError:
    limits += 1
assert limits == 2
print('decimal limits', limits)

invalid_operands = 0
try:
    1 + '2'
except TypeError:
    invalid_operands += 1
try:
    1 < '2'
except TypeError:
    invalid_operands += 1
try:
    pow('2', 3)
except TypeError:
    invalid_operands += 1
try:
    list(range('3'))
except TypeError:
    invalid_operands += 1
try:
    sum([1], '0')
except TypeError:
    invalid_operands += 1
try:
    bin('1')
except TypeError:
    invalid_operands += 1
assert invalid_operands == 6
print('invalid numeric operands', invalid_operands)
