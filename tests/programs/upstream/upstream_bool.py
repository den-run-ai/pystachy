# Adapted from CPython 3.13.16 Lib/test/test_bool.py, class BoolTest: test_repr, test_str,
# test_int, test_float, test_math, test_convert, test_format, test_hasattr, test_isinstance,
# test_contains, test_string, test_boolean, test_fileclosed, test_operator,
# test_convert_to_bool, test_sane_len and test_bool_called_at_least_once, commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b. `is` between bools and ints is rejected here, so assertIs(a, b) and assertIsNot(a, b)
# of bools and ints print repr(a) and assert that it is (or is not) repr(b): a bool's repr is
# True or False, an int's its digits. assertTrue and assertFalse print the value and assert it,
# assertRaises a try statement that prints the exception. An empty display that nothing types is
# an annotated variable. test_fileclosed's TESTFN is a file in a tempfile.mkdtemp() directory.
# test_sane_len's class A, which upstream defines in its loop over badval (a class inside a
# function is rejected), is a module class per value; test_bool_called_at_least_once's f(x) has
# its parameter annotated.
# EXCLUDED upstream cases:
# - test_subclass (class C(bool): inheritance is rejected at compile time, worded "class
#   inheritance is not supported (...)" where CPython says "type 'bool' is not an acceptable
#   base type"; int.__new__), test_repr's eval(repr(...)) (no eval()), test_complex (complex
#   numbers are not supported)
# - test_math's ~false, ~true, eval("~False") and eval("~True"): CPython 3.13 warns there
#   (assertWarns(DeprecationWarning)), on stderr, which Pystachy does not do (its ~ of a bool
#   warns through no warnings module, and gives the same int)
# - test_convert's bool(42, 42): a compile-time error worded "bool() takes exactly one argument (2
#   given)" where CPython says "bool expected at most 1 argument, got 2" (bug: message wording,
#   as #277's); test_keyword_args (bool(x=10): a compile-time error worded "keyword argument 'x'
#   of bool() is not supported" where CPython says "bool() takes no keyword arguments", as
#   #277's)
# - test_callable (callable() is not supported), test_issubclass (issubclass() is not supported),
#   test_types (types as values: bool(t) for t in [bool, complex, ...]), test_real_and_imag
#   (True.real is not supported), test_bool_new (bool.__new__), test_from_bytes (bool.from_bytes)
# - test_operator's operator.is_ and operator.is_not of bools (`is` between bools is rejected)
# - test_marshal, test_pickle and test_picklevalues (marshal, pickle)
# - test_convert_to_bool's Foo and Bar, whose __bool__ returns no bool: compile-time errors with
#   CPython's message where an annotation gives the return type
#   (tests/errors/upstream/upstream_bool_convert_self.py and _str.py), worded "returned NoneType" without
#   it (bug: message, NEW); its Baz and Spam (subclasses of int)
# - test_interpreter_convert_to_bool_raises (Symbol.__gt__ returns a SymbolicBool: a comparison
#   method that returns no bool is rejected at compile time)
# - test_sane_len's A whose __len__ returns 'illegal' (rejected at compile time: "__len__ must
#   return int")
# - test_blocked (__bool__ = None: a class attribute named like a special method, rejected at
#   compile time)
import operator
import os
import tempfile

TESTDIR = tempfile.mkdtemp()
TESTFN = os.path.join(TESTDIR, "upstream_bool.txt")


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def check_is(label: str, got, expected) -> None:
    # assertIs(got, expected) of bools and ints
    print(label, repr(got))
    assert repr(got) == repr(expected), label


def check_is_not(label: str, got, expected) -> None:
    # assertIsNot(got, expected) of bools and ints
    print(label, repr(got))
    assert repr(got) != repr(expected), label


def test_repr() -> None:
    check("repr(False)", repr(False), 'False')
    check("repr(True)", repr(True), 'True')


def test_str() -> None:
    check("str(False)", str(False), 'False')
    check("str(True)", str(True), 'True')


def test_int() -> None:
    check("int(False)", int(False), 0)
    check_is_not("int(False)", int(False), False)
    check("int(True)", int(True), 1)
    check_is_not("int(True)", int(True), True)


def test_float() -> None:
    check("float(False)", float(False), 0.0)
    check_is_not("float(False)", float(False), False)
    check("float(True)", float(True), 1.0)
    check_is_not("float(True)", float(True), True)


def test_math() -> None:
    check("+False", +False, 0)
    check_is_not("+False", +False, False)
    check("-False", -False, 0)
    check_is_not("-False", -False, False)
    check("abs(False)", abs(False), 0)
    check_is_not("abs(False)", abs(False), False)
    check("+True", +True, 1)
    check_is_not("+True", +True, True)
    check("-True", -True, -1)
    check("abs(True)", abs(True), 1)
    check_is_not("abs(True)", abs(True), True)

    check("False+2", False+2, 2)
    check("True+2", True+2, 3)
    check("2+False", 2+False, 2)
    check("2+True", 2+True, 3)

    check("False+False", False+False, 0)
    check_is_not("False+False", False+False, False)
    check("False+True", False+True, 1)
    check_is_not("False+True", False+True, True)
    check("True+False", True+False, 1)
    check_is_not("True+False", True+False, True)
    check("True+True", True+True, 2)

    check("True-True", True-True, 0)
    check_is_not("True-True", True-True, False)
    check("False-False", False-False, 0)
    check_is_not("False-False", False-False, False)
    check("True-False", True-False, 1)
    check_is_not("True-False", True-False, True)
    check("False-True", False-True, -1)

    check("True*1", True*1, 1)
    check("False*1", False*1, 0)
    check_is_not("False*1", False*1, False)

    check("True/1", True/1, 1)
    check_is_not("True/1", True/1, True)
    check("False/1", False/1, 0)
    check_is_not("False/1", False/1, False)

    check("True%1", True%1, 0)
    check_is_not("True%1", True%1, False)
    check("True%2", True%2, 1)
    check_is_not("True%2", True%2, True)
    check("False%1", False%1, 0)
    check_is_not("False%1", False%1, False)

    for b in False, True:
        for i in 0, 1, 2:
            check("%r**%d" % (b, i), b**i, int(b)**i)
            check_is_not("%r**%d" % (b, i), b**i, bool(int(b)**i))

    for a in False, True:
        for b in False, True:
            check_is("%r&%r" % (a, b), a&b, bool(int(a)&int(b)))
            check_is("%r|%r" % (a, b), a|b, bool(int(a)|int(b)))
            check_is("%r^%r" % (a, b), a^b, bool(int(a)^int(b)))
            check("%r&int(%r)" % (a, b), a&int(b), int(a)&int(b))
            check_is_not("%r&int(%r)" % (a, b), a&int(b), bool(int(a)&int(b)))
            check("%r|int(%r)" % (a, b), a|int(b), int(a)|int(b))
            check_is_not("%r|int(%r)" % (a, b), a|int(b), bool(int(a)|int(b)))
            check("%r^int(%r)" % (a, b), a^int(b), int(a)^int(b))
            check_is_not("%r^int(%r)" % (a, b), a^int(b), bool(int(a)^int(b)))
            check("int(%r)&%r" % (a, b), int(a)&b, int(a)&int(b))
            check_is_not("int(%r)&%r" % (a, b), int(a)&b, bool(int(a)&int(b)))
            check("int(%r)|%r" % (a, b), int(a)|b, int(a)|int(b))
            check_is_not("int(%r)|%r" % (a, b), int(a)|b, bool(int(a)|int(b)))
            check("int(%r)^%r" % (a, b), int(a)^b, int(a)^int(b))
            check_is_not("int(%r)^%r" % (a, b), int(a)^b, bool(int(a)^int(b)))

    check_is("1==1", 1==1, True)
    check_is("1==0", 1==0, False)
    check_is("0<1", 0<1, True)
    check_is("1<0", 1<0, False)
    check_is("0<=0", 0<=0, True)
    check_is("1<=0", 1<=0, False)
    check_is("1>0", 1>0, True)
    check_is("1>1", 1>1, False)
    check_is("1>=1", 1>=1, True)
    check_is("0>=1", 0>=1, False)
    check_is("0!=1", 0!=1, True)
    check_is("0!=0", 0!=0, False)

    x = [1]
    check_is("x is x", x is x, True)
    check_is("x is not x", x is not x, False)

    check_is("1 in x", 1 in x, True)
    check_is("0 in x", 0 in x, False)
    check_is("1 not in x", 1 not in x, False)
    check_is("0 not in x", 0 not in x, True)

    y = {1: 2}  # x = {1: 2} upstream: a variable has one type here
    check_is("y is y", y is y, True)
    check_is("y is not y", y is not y, False)

    check_is("1 in y", 1 in y, True)
    check_is("0 in y", 0 in y, False)
    check_is("1 not in y", 1 not in y, False)
    check_is("0 not in y", 0 not in y, True)

    check_is("not True", not True, False)
    check_is("not False", not False, True)


def test_convert() -> None:
    check_is("bool(10)", bool(10), True)
    check_is("bool(1)", bool(1), True)
    check_is("bool(-1)", bool(-1), True)
    check_is("bool(0)", bool(0), False)
    check_is('bool("hello")', bool("hello"), True)
    check_is('bool("")', bool(""), False)
    check_is("bool()", bool(), False)


def test_format() -> None:
    check('"%d" % False', "%d" % False, "0")
    check('"%d" % True', "%d" % True, "1")
    check('"%x" % False', "%x" % False, "0")
    check('"%x" % True', "%x" % True, "1")


def test_hasattr() -> None:
    empty: list[int] = []
    check_is('hasattr([], "append")', hasattr(empty, "append"), True)
    check_is('hasattr([], "wobble")', hasattr(empty, "wobble"), False)


def test_isinstance() -> None:
    check_is("isinstance(True, bool)", isinstance(True, bool), True)
    check_is("isinstance(False, bool)", isinstance(False, bool), True)
    check_is("isinstance(True, int)", isinstance(True, int), True)
    check_is("isinstance(False, int)", isinstance(False, int), True)
    check_is("isinstance(1, bool)", isinstance(1, bool), False)
    check_is("isinstance(0, bool)", isinstance(0, bool), False)


def test_contains() -> None:
    empty: dict[int, int] = {}
    check_is("1 in {}", 1 in empty, False)
    check_is("1 in {1:1}", 1 in {1:1}, True)


def test_string() -> None:
    check_is('"xyz".endswith("z")', "xyz".endswith("z"), True)
    check_is('"xyz".endswith("x")', "xyz".endswith("x"), False)
    check_is('"xyz0123".isalnum()', "xyz0123".isalnum(), True)
    check_is('"@#$%".isalnum()', "@#$%".isalnum(), False)
    check_is('"xyz".isalpha()', "xyz".isalpha(), True)
    check_is('"@#$%".isalpha()', "@#$%".isalpha(), False)
    check_is('"0123".isdigit()', "0123".isdigit(), True)
    check_is('"xyz".isdigit()', "xyz".isdigit(), False)
    check_is('"xyz".islower()', "xyz".islower(), True)
    check_is('"XYZ".islower()', "XYZ".islower(), False)
    check_is('"0123".isdecimal()', "0123".isdecimal(), True)
    check_is('"xyz".isdecimal()', "xyz".isdecimal(), False)
    check_is('"0123".isnumeric()', "0123".isnumeric(), True)
    check_is('"xyz".isnumeric()', "xyz".isnumeric(), False)
    check_is('" ".isspace()', " ".isspace(), True)
    check_is('"\\xa0".isspace()', "\xa0".isspace(), True)
    check_is('"\\u3000".isspace()', "\u3000".isspace(), True)
    check_is('"XYZ".isspace()', "XYZ".isspace(), False)
    check_is('"X".istitle()', "X".istitle(), True)
    check_is('"x".istitle()', "x".istitle(), False)
    check_is('"XYZ".isupper()', "XYZ".isupper(), True)
    check_is('"xyz".isupper()', "xyz".isupper(), False)
    check_is('"xyz".startswith("x")', "xyz".startswith("x"), True)
    check_is('"xyz".startswith("z")', "xyz".startswith("z"), False)


def test_boolean() -> None:
    check("True & 1", True & 1, 1)
    check("isinstance(True & 1, bool)", isinstance(True & 1, bool), False)  # assertNotIsInstance
    check_is("True & True", True & True, True)

    check("True | 1", True | 1, 1)
    check("isinstance(True | 1, bool)", isinstance(True | 1, bool), False)
    check_is("True | True", True | True, True)

    check("True ^ 1", True ^ 1, 0)
    check("isinstance(True ^ 1, bool)", isinstance(True ^ 1, bool), False)
    check_is("True ^ True", True ^ True, False)


def test_fileclosed() -> None:
    try:
        with open(TESTFN, "w", encoding="utf-8") as f:
            check_is("f.closed", f.closed, False)
        check_is("f.closed", f.closed, True)
    finally:
        os.remove(TESTFN)


def test_operator() -> None:
    check_is("operator.truth(0)", operator.truth(0), False)
    check_is("operator.truth(1)", operator.truth(1), True)
    check_is("operator.not_(1)", operator.not_(1), False)
    check_is("operator.not_(0)", operator.not_(0), True)
    empty: list[int] = []
    check_is("operator.contains([], 1)", operator.contains(empty, 1), False)
    check_is("operator.contains([1], 1)", operator.contains([1], 1), True)
    check_is("operator.lt(0, 0)", operator.lt(0, 0), False)
    check_is("operator.lt(0, 1)", operator.lt(0, 1), True)


class Eggs:
    def __len__(self) -> int:
        return -1


def test_convert_to_bool() -> None:
    # Verify that TypeError occurs when bad things are returned
    # from __bool__().  This isn't really a bool test, but
    # it's related.
    try:
        bool(Eggs())
    except ValueError as e:
        print("bool(Eggs()) ValueError:", e)
    else:
        assert False, "expected ValueError"


# test_sane_len's class A, for each badval
class A_minus_one:
    def __len__(self) -> int:
        return -1


class A_shift:
    def __len__(self) -> int:
        return 1 << 32


def test_sane_len() -> None:
    # this test just tests our assumptions about __len__
    # this will start failing if __len__ changes assertions
    # for badval in ['illegal', -1, 1 << 32]:
    try:
        bool(A_minus_one())
    except (Exception) as e_bool:
        try:
            len(A_minus_one())
        except (Exception) as e_len:
            check("str(e_bool)", str(e_bool), str(e_len))
    try:
        bool(A_shift())
    except (Exception) as e_bool:
        try:
            len(A_shift())
        except (Exception) as e_len:
            check("str(e_bool)", str(e_bool), str(e_len))


class X:
    def __init__(self) -> None:
        self.count = 0
    def __bool__(self) -> bool:
        self.count += 1
        return True


def test_bool_called_at_least_once() -> None:
    def f(x: X) -> None:
        if x or True:
            pass

    x = X()
    f(x)
    print("x.count", x.count)
    assert x.count >= 1  # assertGreaterEqual(x.count, 1)


test_repr()
test_str()
test_int()
test_float()
test_math()
test_convert()
test_format()
test_hasattr()
test_isinstance()
test_contains()
test_string()
test_boolean()
test_fileclosed()
test_operator()
test_convert_to_bool()
test_sane_len()
test_bool_called_at_least_once()
os.rmdir(TESTDIR)
