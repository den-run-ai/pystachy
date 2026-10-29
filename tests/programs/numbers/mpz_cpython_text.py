# Adapted from CPython 3.13.16, commit cbc944f4bc59639a444dd971c737788ba2283a91:
# Lib/test/test_long.py (SHA-256 66eeb959a2a1e573f16067fc02d75f22d5344a223bed08033b01612f52d9a11a),
# class LongTest: test_format (with getran(), slow_format() and check_format_1()) and test_long;
# Lib/test/test_int.py (SHA-256 2d947888f306e945ebc12c6817691330528c0bc7a13330b942c9af97fe3075d8),
# class IntTestCases: test_basic's string cases, test_underscores (with test.support.numbers'
# VALID_UNDERSCORE_LITERALS and INVALID_UNDERSCORE_LITERALS), test_error_message and
# test_issue31619, and class IntStrDigitLimitsTests: test_max_str_digits_edge_cases,
# test_max_str_digits, test_power_of_two_bases_unlimited, test_underscores_ignored,
# test_sign_not_counted and test_int_from_other_bases.
# PSF License v2: tests/upstream/CPYTHON-LICENSE.txt; THIRD_PARTY_NOTICES.
# Pystachy port: the text conversions of explicit mpz values, including the cases
# tests/programs/upstream/upstream_int_construct.py and upstream_int_format.py exclude because
# their values need more than 64 bits. int(s[, base]) is mpz(s[, base]). Each test method becomes
# a function of the same name; assertEqual(a, b) prints a and asserts a == b, assertRaises a try
# statement that prints the exception; where upstream loops over many values, each assertion is
# an assert and the loop prints how many it checked. getran() draws its bits with
# random.random(), seeded so that they are the same on every run. mpz formats only decimal
# text: check_format_1 checks str() and repr(), not bin(), oct() or hex(); slow_format's
# divmod(x, base) is x // base and x % base, and int(r) is r.to_int().
# IntStrDigitLimitsTests sets sys.set_int_max_str_digits(2048); mpz's limit is CPython's default,
# 4300 digits, which CPython applies here unchanged: maxdigits is 4300.
# EXCLUDED upstream cases: test_disabled_limit, test_denial_of_service_prevented_int_to_str and
# _str_to_int and test_int_max_str_digits_is_per_interpreter (mpz's limit cannot change; CPU
# timing); test_basic's floats, bytes and int(1, 12); test_error_message's bytes and lone
# surrogates; test_long's invalid bases 2**63, -2**63-1, 2**100 and -2**100 (a base is a native
# int); the other methods are listed in mpz_cpython_int.py and upstream_int_construct.py.
import random
import sys

try:
    from mpz import mpz
except ImportError:
    from mpz_oracle import mpz

SHIFT = 30  # sys.int_info.bits_per_digit
BASE = 2 ** SHIFT
MAXDIGITS = 15
ONE = mpz(1)
ONES = [(ONE << bits) - 1 for bits in range(SHIFT + 1)]

# build some special values
special = [mpz(0), mpz(1), mpz(2), mpz(BASE), mpz(BASE >> 1), mpz(0x5555555555555555),
           mpz("0xaaaaaaaaaaaaaaaa", 0)]
#  some solid strings of one bits
p2 = 4  # 0 and 1 already added
for i in range(2*SHIFT):
    special.append(mpz(p2 - 1))
    p2 = p2 << 1
# add complements & negations
special += [~x for x in special] + [-x for x in special]


def check(label: str, got: mpz, expected: mpz) -> None:
    print(label, got)
    assert got == expected, label


def mpz_raises(s: str, base: int | None = None) -> None:
    # assertRaises(ValueError, int, s[, base])
    try:
        if base is None:
            v = mpz(s)
        else:
            v = mpz(s, base)
    except ValueError as e:
        print("int(%r, %r) ValueError: %s" % (s[:40], base, e))
    else:
        assert False, "expected ValueError, got %s" % v


random.seed(11)


# Get quasi-random long consisting of ndigits digits (in base BASE).
def getran(ndigits: int) -> mpz:
    assert ndigits > 0
    nbits_hi = ndigits * SHIFT
    nbits_lo = nbits_hi - SHIFT + 1
    answer = mpz(0)
    nbits = 0
    r = int(random.random() * (SHIFT * 2)) | 1  # force 1 bits to start
    while nbits < nbits_lo:
        bits = (r >> 1) + 1
        bits = min(bits, nbits_hi - nbits)
        assert 1 <= bits <= SHIFT
        nbits = nbits + bits
        answer = answer << bits
        if r & 1:
            answer = answer | ONES[bits]  # (1 << bits) - 1 upstream
        r = int(random.random() * (SHIFT * 2))
    assert nbits_lo <= nbits <= nbits_hi
    if random.random() < 0.5:
        answer = -answer
    return answer


def slow_format(x: mpz, base: int) -> str:
    digits: list[int] = []
    sign = 0
    if x < 0:
        sign, x = 1, -x
    while x:
        r = x % base  # x, r = divmod(x, base) upstream
        x = x // base
        digits.append(r.to_int())
    digits.reverse()
    digits = digits or [0]
    return '-'[:sign] + \
           {2: '0b', 8: '0o', 10: '', 16: '0x'}[base] + \
           "".join("0123456789abcdef"[i] for i in digits)


FORMATS = [0]


def check_format_1(x: mpz) -> None:
    # (base, mapper) of (10, str) and (10, repr); upstream also (2, bin), (8, oct), (16, hex)
    for got in [str(x), repr(x)]:
        # with self.subTest(x=x, mapper=mapper.__name__):
        expected = slow_format(x, 10)
        assert got == expected, (got, expected)
        # with self.subTest(got=got):
        assert mpz(got, 0) == x, got
        FORMATS[0] += 1


def test_format() -> None:
    for x in special:
        check_format_1(x)
    longest = ""
    for i in range(10):
        for lenx in range(1, MAXDIGITS+1):
            x = getran(lenx)
            check_format_1(x)
            if len(str(x)) > len(longest):
                longest = str(x)
    print("test_format: %d formats; str and repr of %s: %s %s" % (FORMATS[0], special[-1],
          str(special[-1]), repr(special[-1])))
    print("longest:", longest)


L = [
        ('0', 0),
        ('1', 1),
        ('9', 9),
        ('10', 10),
        ('99', 99),
        ('100', 100),
        ('314', 314),
        (' 314', 314),
        ('314 ', 314),
        ('  \t\t  314  \t\t  ', 314),
        (repr(sys.maxsize), sys.maxsize),
        ('  1  ', 1),
]
L_ERRORS = ['  1x', '  1\x02  ', '', ' ', '  \t\t  ', "\u0200"]  # ValueError in L upstream


def test_basic() -> None:
    n = 0
    for s, v in L:
        for sign in "", "+", "-":
            for prefix in "", " ", "\t", "  \t\t  ":
                ss = prefix + sign + s
                vv = mpz(v)
                if sign == "-":
                    vv = -vv
                try:
                    assert mpz(ss) == vv, ss
                    n += 1
                except ValueError:
                    pass
    for s in L_ERRORS:
        for sign in "", "+", "-":
            for prefix in "", " ", "\t", "  \t\t  ":
                try:
                    mpz(prefix + sign + s)
                except ValueError:
                    n += 1
                else:
                    assert False, prefix + sign + s
    print("test_basic: %d strings of L converted, the rest raised ValueError" % n)

    s = repr(-1-sys.maxsize)
    x = mpz(s)
    check("int(%r) + 1" % s, x + 1, mpz(-sys.maxsize))
    # should return int
    check("int(%r)" % s[1:], mpz(s[1:]), mpz(sys.maxsize) + 1)

    # SF bug 434186:  0x80000000/2 != 0x80000000>>1.
    # Worked by accident in Windows release build, but failed in debug build.
    # Failed in all Linux builds.
    x = mpz(-1-sys.maxsize)
    check("x >> 1", x >> 1, x // 2)

    x = mpz('1' * 600)
    assert x == (mpz(10).pow(600) - 1) // 9  # assertIsInstance(x, int) upstream
    print("int('1' * 600) has", len(str(x)), "digits")

    check("int('0o123', 0)", mpz('0o123', 0), mpz(83))
    check("int('0x123', 16)", mpz('0x123', 16), mpz(291))

    # Bug 1679: "0x" is not a valid hex literal
    mpz_raises("0x", 16)
    mpz_raises("0x", 0)
    mpz_raises("0o", 8)
    mpz_raises("0o", 0)
    mpz_raises("0b", 2)
    mpz_raises("0b", 0)


VALID_UNDERSCORE_LITERALS = [
    '0_0_0',
    '4_2',
    '1_0000_0000',
    '0b1001_0100',
    '0xffff_ffff',
    '0o5_7_7',
    '1_00_00.5',
    '1_00_00.5e5',
    '1_00_00e5_1',
    '1e1_0',
    '.1_4',
    '.1_4e1',
    '0b_0',
    '0x_f',
    '0o_5',
    '1_00_00j',
    '1_00_00.5j',
    '1_00_00e5_1j',
    '.1_4j',
    '(1_2.5+3_3j)',
    '(.5_6j)',
]
INVALID_UNDERSCORE_LITERALS = [
    # Trailing underscores:
    '0_',
    '42_',
    '1.4j_',
    '0x_',
    '0b1_',
    '0xf_',
    '0o5_',
    '0 if 1_Else 1',
    # Underscores in the base selector:
    '0_b0',
    '0_xf',
    '0_o5',
    # Old-style octal, still disallowed:
    '0_7',
    '09_99',
    # Multiple consecutive underscores:
    '4_______2',
    '0.1__4',
    '0.1__4j',
    '0b1001__0100',
    '0xffff__ffff',
    '0x___',
    '0o5__77',
    '1e1__0',
    '1e1__0j',
    # Underscore right before a dot:
    '1_.4',
    '1_.4j',
    # Underscore right after a dot:
    '1._4',
    '1._4j',
    '._5',
    '._5j',
    # Underscore right after a sign:
    '1.0e+_1',
    '1.0e+_1j',
    # Underscore right before j:
    '1.4_j',
    '1.4e5_j',
    # Underscore right before e:
    '1_e1',
    '1.4_e1',
    '1.4_e1j',
    # Underscore right after e:
    '1e_1',
    '1.4e_1',
    '1.4e_1j',
    # Complex cases with parens:
    '(1+1.5_j_)',
    '(1+1.5_j)',
]
# eval(lit) of the literals that test_underscores evaluates
EVAL = {
    '0_0_0': 0_0_0,
    '4_2': 4_2,
    '1_0000_0000': 1_0000_0000,
    '0b1001_0100': 0b1001_0100,
    '0xffff_ffff': 0xffff_ffff,
    '0o5_7_7': 0o5_7_7,
    '0b_0': 0b_0,
    '0x_f': 0x_f,
    '0o_5': 0o_5,
}


def test_underscores() -> None:
    for lit in VALID_UNDERSCORE_LITERALS:
        if any(ch in lit for ch in '.eEjJ'):
            continue
        check("int(%r, 0)" % lit, mpz(lit, 0), mpz(EVAL[lit]))
        check("int(%r, 0)" % lit.replace('_', ''), mpz(lit, 0), mpz(lit.replace('_', ''), 0))
    for lit in INVALID_UNDERSCORE_LITERALS:
        if any(ch in lit for ch in '.eEjJ'):
            continue
        mpz_raises(lit, 0)
    # Additional test cases with bases != 0, only for the constructor:
    check('int("1_00", 3)', mpz("1_00", 3), mpz(9))
    check('int("0_100")', mpz("0_100"), mpz(100))  # not valid as a literal!
    mpz_raises("_100")
    mpz_raises("+_100")
    mpz_raises("1__00")
    mpz_raises("100_")


def test_error_message() -> None:
    def check_msg(s: str, base: int | None = None) -> None:
        try:
            if base is None:
                mpz(s)
            else:
                mpz(s, base)
        except ValueError as e:
            print("int(%r, %r):" % (s, base), repr(str(e)))
            assert str(e) == "invalid literal for int() with base %d: %r" % (10 if base is None else base, s)
        else:
            assert False, "int(%r, %r)" % (s, base)

    check_msg('\xbd')
    check_msg('123\xbd')
    check_msg('  123 456  ')

    check_msg('123\x00')
    # SF bug 1545497: embedded NULs were not detected with explicit base
    check_msg('123\x00', 10)
    check_msg('123\x00 245', 20)
    check_msg('123\x00 245', 16)
    check_msg('123\x00245', 20)
    check_msg('123\x00245', 16)


def test_issue31619() -> None:
    check("int('1_0_1_..._1', 2)", mpz('1_0_1_0_1_0_1_0_1_0_1_0_1_0_1_0_1_0_1_0_1_0_1_0_1_0_1_0_1_0_1', 2),
          mpz(0b1010101010101010101010101010101))
    check("int('1_2_3_4_5_6_7_0_1_2_3', 8)", mpz('1_2_3_4_5_6_7_0_1_2_3', 8), mpz(0o12345670123))
    check("int('1_2_3_4_5_6_7_8_9', 16)", mpz('1_2_3_4_5_6_7_8_9', 16), mpz(0x123456789))
    check("int('1_2_3_4_5_6_7', 32)", mpz('1_2_3_4_5_6_7', 32), mpz(1144132807))


# Lib/test/test_long.py, LongTest
def test_long() -> None:
    # Check conversions from string
    LL = [
            ('1' + '0'*20, mpz(10).pow(20)),
            ('1' + '0'*100, mpz(10).pow(100))
    ]
    n = 0
    for s, v in LL:
        for sign in "", "+", "-":
            for prefix in "", " ", "\t", "  \t\t  ":
                ss = prefix + sign + s
                vv = v
                if sign == "-":
                    vv = -v
                try:
                    assert mpz(ss) == vv, ss
                    n += 1
                except ValueError:
                    pass
    print("test_long: %d strings of LL converted; 10**100 is" % n, LL[1][1])

    # trailing L should no longer be accepted...
    mpz_raises('123L')
    mpz_raises('123l')
    mpz_raises('0L')
    mpz_raises('-37L')
    mpz_raises('0x32L', 16)
    mpz_raises('1L', 21)
    # ... but it's just a normal digit if base >= 22
    check("int('1L', 22)", mpz('1L', 22), mpz(43))

    # tests with base 0
    check("int('000', 0)", mpz('000', 0), mpz(0))
    check("int('0o123', 0)", mpz('0o123', 0), mpz(83))
    check("int('0x123', 0)", mpz('0x123', 0), mpz(291))
    check("int('0b100', 0)", mpz('0b100', 0), mpz(4))
    check("int(' 0O123   ', 0)", mpz(' 0O123   ', 0), mpz(83))
    check("int(' 0X123  ', 0)", mpz(' 0X123  ', 0), mpz(291))
    check("int(' 0B100 ', 0)", mpz(' 0B100 ', 0), mpz(4))
    check("int('0', 0)", mpz('0', 0), mpz(0))
    check("int('+0', 0)", mpz('+0', 0), mpz(0))
    check("int('-0', 0)", mpz('-0', 0), mpz(0))
    check("int('00', 0)", mpz('00', 0), mpz(0))
    mpz_raises('08', 0)
    mpz_raises('-012395', 0)

    # invalid bases
    invalid_bases = [-909,
                      2**31-1, 2**31, -2**31, -2**31-1,
                      9223372036854775807, -9223372036854775807-1,  # 2**63-1, -2**63
                      ]
    for base in invalid_bases:
        mpz_raises('42', base)

    # Invalid unicode string
    # See bpo-34087
    mpz_raises('\u3053\u3093\u306b\u3061\u306f')


# Lib/test/test_int.py, IntStrDigitLimitsTests
maxdigits = 4300  # sys.get_int_max_str_digits(), 2048 upstream


def raises_text(label: str, x: mpz) -> None:
    # with self.assertRaises(ValueError): str(x)
    try:
        s = str(x)
    except ValueError as e:
        print(label, "ValueError:", e)
    else:
        assert False, "expected ValueError, got %d digits" % len(s)


def test_max_str_digits_edge_cases() -> None:
    """Ignore the +/- sign and space padding."""
    check("int('1' * maxdigits) % 1000", mpz('1' * maxdigits) % 1000, mpz(111))
    check("int(' ' + '1' * maxdigits) % 1000", mpz(' ' + '1' * maxdigits) % 1000, mpz(111))
    check("int('1' * maxdigits + ' ') % 1000", mpz('1' * maxdigits + ' ') % 1000, mpz(111))
    check("int('+' + '1' * maxdigits) % 1000", mpz('+' + '1' * maxdigits) % 1000, mpz(111))
    check("int('-' + '1' * maxdigits) % 1000", mpz('-' + '1' * maxdigits) % 1000, mpz(889))
    print("len(str(10 ** (maxdigits - 1)))", len(str(mpz(10).pow(maxdigits - 1))))
    assert len(str(mpz(10).pow(maxdigits - 1))) == maxdigits


def test_max_str_digits() -> None:
    mpz_raises('1' * (maxdigits + 1))
    mpz_raises(' ' + '1' * (maxdigits + 1))
    mpz_raises('1' * (maxdigits + 1) + ' ')
    mpz_raises('+' + '1' * (maxdigits + 1))
    mpz_raises('-' + '1' * (maxdigits + 1))
    mpz_raises('1' * (maxdigits + 1))

    i = mpz(10).pow(maxdigits)
    raises_text("str(10 ** maxdigits)", i)


def test_power_of_two_bases_unlimited() -> None:
    """The limit does not apply to power of 2 bases."""
    for base in (2, 4, 8, 16, 32):
        # with self.subTest(base=base):
        x = mpz('1' * (maxdigits + 1), base)
        assert maxdigits < 100_000
        y = mpz('1' * 100_000, base)
        print("int('1' * (maxdigits + 1), %d) has %d bits, int('1' * 100_000, %d) %d"
              % (base, x.bit_length(), base, y.bit_length()))


def test_underscores_ignored() -> None:
    triples = maxdigits // 3
    s = '111' * triples
    s_ = '1_11' * triples
    check("int(s) % 1000", mpz(s) % 1000, mpz(111))  # succeeds
    assert mpz(s_) == mpz(s)  # succeeds
    mpz_raises(f'{s}111')
    mpz_raises(f'{s_}_111')


def test_sign_not_counted() -> None:
    max_digits = maxdigits
    s = '5' * max_digits
    i = mpz(s)
    pos_i = mpz(f'+{s}')
    assert i == pos_i
    neg_i = mpz(f'-{s}')
    assert -pos_i == neg_i
    print("str(pos_i) has", len(str(pos_i)), "characters, str(neg_i)", len(str(neg_i)))


def _other_base_helper(base: int) -> None:
    max_digits = maxdigits
    s = '2' * max_digits
    i = mpz(s, base)
    if base > 10:
        raises_text("str(int('2' * max_digits, %d))" % base, i)
    elif base < 10:
        print("str(int('2' * max_digits, %d)) has %d digits" % (base, len(str(i))))
    mpz_raises(f'{s}1', base)


def test_int_from_other_bases() -> None:
    base = 3
    # with self.subTest(base=base):
    _other_base_helper(base)
    base = 36
    # with self.subTest(base=base):
    _other_base_helper(base)


test_format()
test_basic()
test_underscores()
test_error_message()
test_issue31619()
test_long()
test_max_str_digits_edge_cases()
test_max_str_digits()
test_power_of_two_bases_unlimited()
test_underscores_ignored()
test_sign_not_counted()
test_int_from_other_bases()
