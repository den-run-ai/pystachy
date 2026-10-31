# Adapted from CPython 3.13.16 Lib/test/test_exceptions.py, class ExceptionTests: testRaising
# (with raise_catch()), testAttributes, testKeywordArgs and test_str (with the module's
# NaiveException and SlottedNaiveException), commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, assertTrue(x) prints x and asserts it, assertRaises a try statement that prints the
# exception. A builtin exception class is no value here, so each self.raise_catch(exc, excname)
# is written out, with the class named in its raise and except, and exc.__name__ is
# type(err).__name__ of the exception it caught. testRaising's x, a list, a dict and an int
# upstream, is three variables (a variable has one type here). testAttributes makes each
# exception with a call of its class (e = exc(*args, **kwargs)) and checks the args it expects
# through repr(e), which shows them (e.args is not supported); NaiveException's x is a field.
# Test-method classes are module classes, and an annotation is added where the subset needs one.
# EXCLUDED upstream cases (see also tests/programs/upstream/upstream_exceptions_flow.py):
# - testRaising's getattr(sys, "undefined_attribute") (no getattr()), its EOFError of
#   marshal.loads(b'') (no marshal), exec('/\n') and compile() of a TabError (no exec() or
#   compile()), and `x += x` 128 times from 1 (2**128 does not fit in 64 bits here:
#   OverflowError); its `[] + ()` (a compile-time error here, "cannot infer the type of an
#   empty list", where CPython says 'can only concatenate list (not "tuple") to list');
#   `x = undefined_variable` is a compile-time error with CPython's message
#   (tests/errors/upstream/upstream_exceptions_undefined_variable.py); __import__("undefined_module")
#   is the statement import undefined_module, in a try statement
# - testAttributes' attributes other than args and x (code, errno, strerror, filename,
#   filename2, msg, text, lineno, offset, end_lineno, end_offset, print_file_and_line, name,
#   obj: not supported), type(e).__module__ and its pickle round trips; its cases
#   OSError('foo', 'bar', 'baz', None, 'quux') (more than three arguments for OSError: not
#   supported), SyntaxError() of several arguments, the attributes of UnicodeEncodeError and
#   UnicodeDecodeError (also of a bytearray and bytes) and UnicodeTranslateError (not supported), and
#   WindowsError (Windows only)
# - testKeywordArgs' BaseException(a=1): a compile-time error with CPython's message
#   (tests/errors/upstream/upstream_exceptions_keyword_args.py)
# - test_str's str(Exception) (a builtin exception class is no value here)
# - testSyntaxErrorMessage, testSyntaxErrorMissingParens, test_error_offset_continuation_characters,
#   testSyntaxErrorRange and testSyntaxErrorOffset (compile() of fragments): their fragments are
#   tests/errors/upstream/upstream_exceptions_syntax_*.py where Pystachy reports CPython's line and
#   message, but for these:
#   - exec "old style", exec f(a+b,c) and ages = {'Alice'=22, 'Bob'=23}: "invalid syntax" where
#     CPython's parser gives a hint (documented)
#   - the tab of exec "mixed tabs and spaces" and of def fact(x)'s return x! (tabs in
#     indentation are rejected, documented)
#   - the Greek and combining-character names of testSyntaxErrorRange's cases and of
#     testSyntaxErrorOffset's 0xI (non-ASCII identifiers are rejected, documented)
#   - the cp1251 and iso8859-7 coding declarations (rejected, documented; nor would they be on a
#     fixture's first two lines), and the UTF-8 BOM before #coding: utf8 (a BOM must start the
#     file, where a fixture's first line goes)
#   - case {**rest, "key": value} (match statements are rejected, documented)
#   - test_error_offset_continuation_characters' "\\\n"(1 for c in I,\\\n\\: "Generator
#     expression must be parenthesized", where CPython reports "'(' was never closed" (bug, NEW)
# - testMemoryErrorBigSource (bigmemtest), testSettingException and test_MemoryError (_testcapi),
#   test_WindowsError and test_windows_message (Windows: on POSIX upstream reads WindowsError
#   and finds it unbound, a compile-time error here)
# - test_setstate, test_invalid_setstate, test_notes, testWithTraceback, testInvalidTraceback,
#   test_invalid_setattr, test_object_attributes, test_invalid_delattr,
#   testNoneClearsTracebackAttr, testChainingAttrs and testChainingDescriptors: __setstate__,
#   add_note() and __notes__, with_traceback() and __traceback__, setattr() and delattr(),
#   __cause__, __context__ and __suppress_context__ (an exception's attributes and BaseException's
#   methods other than __str__ and __repr__ are not supported)
# - testInfiniteRecursion, test_recursion_in_except_handler and test_badisinstance's
#   recursion (covered separately by bounded native recursion guard cases; exact native frame
#   depth differs), test_badisinstance's metaclass, test_trashcan_recursion,
#   test_recursion_normalizing_exception, test_recursion_normalizing_infinite_exception,
#   test_recursion_normalizing_with_no_memory, test_memory_error_in_PyErr_PrintEx,
#   test_memory_error_in_subinterp and test_exec_set_nomemory_hang (_testcapi,
#   _testinternalcapi, subprocesses, set_nomemory), test_exception_with_doc,
#   test_memory_error_cleanup and test_recursion_error_cleanup (_testcapi, weakref, gc)
import sys


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def check_true(label: str, got) -> None:
    print(label, repr(got))
    assert got, label


class NaiveException(Exception):
    def __init__(self, x: str) -> None:
        self.x = x


class SlottedNaiveException(Exception):
    __slots__ = ('x',)
    def __init__(self, x: str) -> None:
        self.x = x


def raise_catch(exc: str, buf1: str, buf2: str, name: str) -> None:
    # the asserts of raise_catch(self, exc, excname), whose raise and except statements are
    # written out in testRaising
    print(exc, repr(buf1), name)
    assert buf1 == buf2, exc
    assert name == exc, exc  # self.assertEqual(exc.__name__, excname)


def testRaising() -> None:
    # self.raise_catch(AttributeError, "AttributeError")
    try:
        raise AttributeError("spam")
    except AttributeError as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise AttributeError("spam")
    except AttributeError as err:
        buf2 = str(err)
    raise_catch("AttributeError", buf1, buf2, name)
    # self.assertRaises(AttributeError, getattr, sys, "undefined_attribute"): no getattr()

    # self.raise_catch(EOFError, "EOFError")
    try:
        raise EOFError("spam")
    except EOFError as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise EOFError("spam")
    except EOFError as err:
        buf2 = str(err)
    raise_catch("EOFError", buf1, buf2, name)
    # its marshal.loads(b'') with TESTFN open: no marshal

    # self.raise_catch(OSError, "OSError")
    try:
        raise OSError("spam")
    except OSError as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise OSError("spam")
    except OSError as err:
        buf2 = str(err)
    raise_catch("OSError", buf1, buf2, name)
    try:
        open('this file does not exist', 'r')
    except OSError as e:
        print("open('this file does not exist', 'r') OSError:", e)
    else:
        assert False, "expected OSError"

    # self.raise_catch(ImportError, "ImportError")
    try:
        raise ImportError("spam")
    except ImportError as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise ImportError("spam")
    except ImportError as err:
        buf2 = str(err)
    raise_catch("ImportError", buf1, buf2, name)
    try:
        import undefined_module  # __import__("undefined_module")
    except ImportError:
        print('import undefined_module: ImportError')

    # self.raise_catch(IndexError, "IndexError")
    try:
        raise IndexError("spam")
    except IndexError as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise IndexError("spam")
    except IndexError as err:
        buf2 = str(err)
    raise_catch("IndexError", buf1, buf2, name)
    x: list[int] = []
    try:
        x[10]  # x.__getitem__(10)
    except IndexError as e:
        print("x[10] IndexError:", e)
    else:
        assert False, "expected IndexError"

    # self.raise_catch(KeyError, "KeyError")
    try:
        raise KeyError("spam")
    except KeyError as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise KeyError("spam")
    except KeyError as err:
        buf2 = str(err)
    raise_catch("KeyError", buf1, buf2, name)
    x2: dict[str, int] = {}  # x = {}: a variable has one type here
    try:
        x2['key']  # x.__getitem__('key')
    except KeyError as e:
        print("x['key'] KeyError:", e)
    else:
        assert False, "expected KeyError"

    # self.raise_catch(KeyboardInterrupt, "KeyboardInterrupt")
    try:
        raise KeyboardInterrupt("spam")
    except KeyboardInterrupt as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise KeyboardInterrupt("spam")
    except KeyboardInterrupt as err:
        buf2 = str(err)
    raise_catch("KeyboardInterrupt", buf1, buf2, name)

    # self.raise_catch(MemoryError, "MemoryError")
    try:
        raise MemoryError("spam")
    except MemoryError as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise MemoryError("spam")
    except MemoryError as err:
        buf2 = str(err)
    raise_catch("MemoryError", buf1, buf2, name)

    # self.raise_catch(NameError, "NameError")
    try:
        raise NameError("spam")
    except NameError as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise NameError("spam")
    except NameError as err:
        buf2 = str(err)
    raise_catch("NameError", buf1, buf2, name)
    # try: x = undefined_variable / except NameError: pass: a compile-time error here,
    # with CPython's message (tests/errors/upstream/upstream_exceptions_undefined_variable.py)

    # self.raise_catch(OverflowError, "OverflowError")
    try:
        raise OverflowError("spam")
    except OverflowError as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise OverflowError("spam")
    except OverflowError as err:
        buf2 = str(err)
    raise_catch("OverflowError", buf1, buf2, name)
    # x = 1; for dummy in range(128): x += x  # this simply shouldn't blow up
    # (2**128 does not fit in 64 bits here: OverflowError)

    # self.raise_catch(RuntimeError, "RuntimeError")
    try:
        raise RuntimeError("spam")
    except RuntimeError as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise RuntimeError("spam")
    except RuntimeError as err:
        buf2 = str(err)
    raise_catch("RuntimeError", buf1, buf2, name)

    # self.raise_catch(RecursionError, "RecursionError")
    try:
        raise RecursionError("spam")
    except RecursionError as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise RecursionError("spam")
    except RecursionError as err:
        buf2 = str(err)
    raise_catch("RecursionError", buf1, buf2, name)

    # self.raise_catch(SyntaxError, "SyntaxError")
    try:
        raise SyntaxError("spam")
    except SyntaxError as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise SyntaxError("spam")
    except SyntaxError as err:
        buf2 = str(err)
    raise_catch("SyntaxError", buf1, buf2, name)
    # try: exec('/\n') / except SyntaxError: pass: no exec()

    # self.raise_catch(IndentationError, "IndentationError")
    try:
        raise IndentationError("spam")
    except IndentationError as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise IndentationError("spam")
    except IndentationError as err:
        buf2 = str(err)
    raise_catch("IndentationError", buf1, buf2, name)

    # self.raise_catch(TabError, "TabError")
    try:
        raise TabError("spam")
    except TabError as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise TabError("spam")
    except TabError as err:
        buf2 = str(err)
    raise_catch("TabError", buf1, buf2, name)
    # compile() of a source indented with tabs: no compile()

    # self.raise_catch(SystemError, "SystemError")
    try:
        raise SystemError("spam")
    except SystemError as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise SystemError("spam")
    except SystemError as err:
        buf2 = str(err)
    raise_catch("SystemError", buf1, buf2, name)

    # self.raise_catch(SystemExit, "SystemExit")
    try:
        raise SystemExit("spam")
    except SystemExit as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise SystemExit("spam")
    except SystemExit as err:
        buf2 = str(err)
    raise_catch("SystemExit", buf1, buf2, name)
    try:
        sys.exit(0)
    except SystemExit as e:
        print("sys.exit(0) SystemExit:", repr(e))
    else:
        assert False, "expected SystemExit"

    # self.raise_catch(TypeError, "TypeError")
    try:
        raise TypeError("spam")
    except TypeError as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise TypeError("spam")
    except TypeError as err:
        buf2 = str(err)
    raise_catch("TypeError", buf1, buf2, name)
    # try: [] + () / except TypeError: pass: a compile-time error here

    # self.raise_catch(ValueError, "ValueError")
    try:
        raise ValueError("spam")
    except ValueError as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise ValueError("spam")
    except ValueError as err:
        buf2 = str(err)
    raise_catch("ValueError", buf1, buf2, name)
    try:
        chr(17<<16)
    except ValueError as e:
        print("chr(17<<16) ValueError:", e)
    else:
        assert False, "expected ValueError"

    # self.raise_catch(ZeroDivisionError, "ZeroDivisionError")
    try:
        raise ZeroDivisionError("spam")
    except ZeroDivisionError as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise ZeroDivisionError("spam")
    except ZeroDivisionError as err:
        buf2 = str(err)
    raise_catch("ZeroDivisionError", buf1, buf2, name)
    try: x3 = 1/0
    except ZeroDivisionError as e: print("1/0 ZeroDivisionError:", e)

    # self.raise_catch(Exception, "Exception")
    try:
        raise Exception("spam")
    except Exception as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise Exception("spam")
    except Exception as err:
        buf2 = str(err)
    raise_catch("Exception", buf1, buf2, name)
    try: x3 = 1/0
    except Exception as e: print("1/0 Exception:", e)

    # self.raise_catch(StopAsyncIteration, "StopAsyncIteration")
    try:
        raise StopAsyncIteration("spam")
    except StopAsyncIteration as err:
        buf1, name = str(err), type(err).__name__
    try:
        raise StopAsyncIteration("spam")
    except StopAsyncIteration as err:
        buf2 = str(err)
    raise_catch("StopAsyncIteration", buf1, buf2, name)


def check_args(e: BaseException, args: str) -> None:
    # Verify no ref leaks in Exc_str()
    s = str(e)
    print(repr(e), repr(s))
    # for checkArgName in expected: ... 'args': repr(e) is the class's name and the args
    if args != "":
        assert repr(e) == type(e).__name__ + args, (repr(e), args)


def testAttributes() -> None:
    # test that exception attributes are happy

    # (exc, args, kwargs, expected): the exception, made as exc(*args, **kwargs), and the
    # expected args, as BaseException.__repr__ shows them after the class's name ("" where
    # upstream expects no args)
    exceptionList: list[BaseException] = [
        BaseException(),  # {'args' : ()}
        BaseException(1),  # {'args' : (1,)}
        BaseException('foo'),  # {'args' : ('foo',)}
        BaseException('foo', 1),  # {'args' : ('foo', 1)}
        SystemExit('foo'),  # {'args' : ('foo',), 'code' : 'foo'}
        OSError('foo'),  # {'args' : ('foo',), 'filename' : None, ...}
        OSError('foo', 'bar'),  # {'args' : ('foo', 'bar'), ...}
        OSError('foo', 'bar', 'baz'),  # {'args' : ('foo', 'bar'), 'filename' : 'baz', ...}
        OSError('errnoStr', 'strErrorStr', 'filenameStr'),  # {'args' : ('errnoStr', 'strErrorStr'), ...}
        OSError(1, 'strErrorStr', 'filenameStr'),  # {'args' : (1, 'strErrorStr'), 'errno' : 1, ...}
        SyntaxError(),  # {'msg' : None, 'text' : None, ...}
        SyntaxError('msgStr'),  # {'args' : ('msgStr',), 'text' : None, ...}
        UnicodeError(),  # {'args' : (),}
        AttributeError('foo', name='name', obj='obj'),  # dict(args=('foo',), name='name', obj='obj')
    ]
    expected_args = [
        "()",
        "(1)",
        "('foo')",
        "('foo', 1)",
        "('foo')",
        "('foo')",
        "('foo', 'bar')",
        "('foo', 'bar')",
        "('errnoStr', 'strErrorStr')",
        "(1, 'strErrorStr')",
        "",
        "('msgStr')",
        "()",
        "('foo')",
    ]
    for e, args in zip(exceptionList, expected_args):
        check_args(e, args)

    e1 = NaiveException('foo')  # {'args': ('foo',), 'x': 'foo'}
    print(repr(e1), repr(str(e1)))
    check("NaiveException('foo')", repr(e1), "NaiveException('foo')")
    check("NaiveException('foo').x", e1.x, 'foo')
    e2 = SlottedNaiveException('foo')  # {'args': ('foo',), 'x': 'foo'}
    print(repr(e2), repr(str(e2)))
    check("SlottedNaiveException('foo')", repr(e2), "SlottedNaiveException('foo')")
    check("SlottedNaiveException('foo').x", e2.x, 'foo')


class DerivedException(BaseException):
    def __init__(self, fancy_arg: int) -> None:
        BaseException.__init__(self)
        self.fancy_arg = fancy_arg


def testKeywordArgs() -> None:
    # test that builtin exception don't take keyword args,
    # but user-defined subclasses can if they want
    x = DerivedException(fancy_arg=42)
    check("x.fancy_arg", x.fancy_arg, 42)


def test_str() -> None:
    # Make sure both instances and classes have a str representation.
    check_true("str(Exception('a'))", str(Exception('a')))
    check_true("str(Exception('a', 'b'))", str(Exception('a', 'b')))


testRaising()
testAttributes()
testKeywordArgs()
test_str()
