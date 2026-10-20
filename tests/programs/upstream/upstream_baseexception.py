# Adapted from CPython 3.13.16 Lib/test/test_baseexception.py, class ExceptionClassTests:
# test_inheritance (with Lib/test/exception_hierarchy.txt, below), interface_test_driver,
# test_interface_single_arg, test_interface_multi_arg and test_interface_no_arg, commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, assertTrue(x) prints x and asserts it. A builtin exception class is no value here, and
# getattr() and issubclass() are not supported, so test_inheritance's getattr(builtins, name) is
# make(name), which makes an exception of that class, and issubclass(exc, sup) is
# is_instance(make(name), sup_name), which tests it with isinstance() against the class sup
# names. Its tree is the text of exception_hierarchy.txt with ASCII in place of its box-drawing
# characters (+--, `-- and |), as Pystachy's str.rindex() and slices count bytes, not characters
# (a documented deviation, #120). exc.__class__.__name__ is type(exc).__name__.
# EXCLUDED upstream cases:
# - test_inheritance's exc_set (builtins.__dict__, issubclass(): the check that each builtin
#   exception class is in the file, and the file's in builtins), its
#   verify_instance_interface(exc()) (hasattr() of an exception's args is not supported), and
#   its issubclass() of BaseExceptionGroup, ExceptionGroup, UnicodeDecodeError,
#   UnicodeEncodeError and UnicodeTranslateError, which Pystachy cannot make (their calls of
#   several arguments, and ExceptionGroup, are not supported; upstream calls none of them
#   without arguments either)
# - the interface tests' len(exc.args) and exc.args (an exception's args are not supported;
#   repr(exc.args) is repr(args), which upstream checks exc.args equals)
# - test_builtins_new_style (issubclass(Exception, object): no issubclass(), and a builtin
#   exception class is no value), test_setstate_refcount_no_crash (__setstate__, a subclass of
#   str with __hash__, gc)
# - UsageTests: test_raise_string and test_catch_non_BaseException's class (also in a tuple) are
#   compile-time errors with CPython's message (tests/errors/upstream/upstream_baseexception_*.py);
#   test_raise_new_style_non_exception (rejected at compile time, worded "'NewStyleClass' is not
#   an exception class: exceptions must derive from BaseException" where CPython says
#   "exceptions must derive from BaseException"), test_catch_non_BaseException's instance,
#   test_catch_BaseException_instance and test_catch_string (compile-time errors worded "an
#   except clause needs exception classes: a name, or a tuple of names", where CPython says
#   "catching classes that do not inherit from BaseException is not allowed")


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def check_true(label: str, got: bool) -> None:
    print(label, repr(got))
    assert got, label


# Lib/test/exception_hierarchy.txt, with +--, `-- and | for its box-drawing characters
EXCEPTION_HIERARCHY = """\
BaseException
 +-- BaseExceptionGroup
 +-- GeneratorExit
 +-- KeyboardInterrupt
 +-- SystemExit
 `-- Exception
      +-- ArithmeticError
      |    +-- FloatingPointError
      |    +-- OverflowError
      |    `-- ZeroDivisionError
      +-- AssertionError
      +-- AttributeError
      +-- BufferError
      +-- EOFError
      +-- ExceptionGroup [BaseExceptionGroup]
      +-- ImportError
      |    `-- ModuleNotFoundError
      +-- LookupError
      |    +-- IndexError
      |    `-- KeyError
      +-- MemoryError
      +-- NameError
      |    `-- UnboundLocalError
      +-- OSError
      |    +-- BlockingIOError
      |    +-- ChildProcessError
      |    +-- ConnectionError
      |    |    +-- BrokenPipeError
      |    |    +-- ConnectionAbortedError
      |    |    +-- ConnectionRefusedError
      |    |    `-- ConnectionResetError
      |    +-- FileExistsError
      |    +-- FileNotFoundError
      |    +-- InterruptedError
      |    +-- IsADirectoryError
      |    +-- NotADirectoryError
      |    +-- PermissionError
      |    +-- ProcessLookupError
      |    `-- TimeoutError
      +-- ReferenceError
      +-- RuntimeError
      |    +-- NotImplementedError
      |    +-- PythonFinalizationError
      |    `-- RecursionError
      +-- StopAsyncIteration
      +-- StopIteration
      +-- SyntaxError
      |    `-- IndentationError
      |         `-- TabError
      +-- SystemError
      +-- TypeError
      +-- ValueError
      |    `-- UnicodeError
      |         +-- UnicodeDecodeError
      |         +-- UnicodeEncodeError
      |         `-- UnicodeTranslateError
      `-- Warning
           +-- BytesWarning
           +-- DeprecationWarning
           +-- EncodingWarning
           +-- FutureWarning
           +-- ImportWarning
           +-- PendingDeprecationWarning
           +-- ResourceWarning
           +-- RuntimeWarning
           +-- SyntaxWarning
           +-- UnicodeWarning
           `-- UserWarning"""


def make(name: str) -> BaseException:
    # getattr(builtins, name)(): an exception of the class that name names
    if name == 'BaseException':
        return BaseException()
    if name == 'GeneratorExit':
        return GeneratorExit()
    if name == 'KeyboardInterrupt':
        return KeyboardInterrupt()
    if name == 'SystemExit':
        return SystemExit()
    if name == 'Exception':
        return Exception()
    if name == 'ArithmeticError':
        return ArithmeticError()
    if name == 'FloatingPointError':
        return FloatingPointError()
    if name == 'OverflowError':
        return OverflowError()
    if name == 'ZeroDivisionError':
        return ZeroDivisionError()
    if name == 'AssertionError':
        return AssertionError()
    if name == 'AttributeError':
        return AttributeError()
    if name == 'BufferError':
        return BufferError()
    if name == 'EOFError':
        return EOFError()
    if name == 'ImportError':
        return ImportError()
    if name == 'ModuleNotFoundError':
        return ModuleNotFoundError()
    if name == 'LookupError':
        return LookupError()
    if name == 'IndexError':
        return IndexError()
    if name == 'KeyError':
        return KeyError()
    if name == 'MemoryError':
        return MemoryError()
    if name == 'NameError':
        return NameError()
    if name == 'UnboundLocalError':
        return UnboundLocalError()
    if name == 'OSError':
        return OSError()
    if name == 'BlockingIOError':
        return BlockingIOError()
    if name == 'ChildProcessError':
        return ChildProcessError()
    if name == 'ConnectionError':
        return ConnectionError()
    if name == 'BrokenPipeError':
        return BrokenPipeError()
    if name == 'ConnectionAbortedError':
        return ConnectionAbortedError()
    if name == 'ConnectionRefusedError':
        return ConnectionRefusedError()
    if name == 'ConnectionResetError':
        return ConnectionResetError()
    if name == 'FileExistsError':
        return FileExistsError()
    if name == 'FileNotFoundError':
        return FileNotFoundError()
    if name == 'InterruptedError':
        return InterruptedError()
    if name == 'IsADirectoryError':
        return IsADirectoryError()
    if name == 'NotADirectoryError':
        return NotADirectoryError()
    if name == 'PermissionError':
        return PermissionError()
    if name == 'ProcessLookupError':
        return ProcessLookupError()
    if name == 'TimeoutError':
        return TimeoutError()
    if name == 'ReferenceError':
        return ReferenceError()
    if name == 'RuntimeError':
        return RuntimeError()
    if name == 'NotImplementedError':
        return NotImplementedError()
    if name == 'PythonFinalizationError':
        return PythonFinalizationError()
    if name == 'RecursionError':
        return RecursionError()
    if name == 'StopAsyncIteration':
        return StopAsyncIteration()
    if name == 'StopIteration':
        return StopIteration()
    if name == 'SyntaxError':
        return SyntaxError()
    if name == 'IndentationError':
        return IndentationError()
    if name == 'TabError':
        return TabError()
    if name == 'SystemError':
        return SystemError()
    if name == 'TypeError':
        return TypeError()
    if name == 'ValueError':
        return ValueError()
    if name == 'UnicodeError':
        return UnicodeError()
    if name == 'Warning':
        return Warning()
    if name == 'BytesWarning':
        return BytesWarning()
    if name == 'DeprecationWarning':
        return DeprecationWarning()
    if name == 'EncodingWarning':
        return EncodingWarning()
    if name == 'FutureWarning':
        return FutureWarning()
    if name == 'ImportWarning':
        return ImportWarning()
    if name == 'PendingDeprecationWarning':
        return PendingDeprecationWarning()
    if name == 'ResourceWarning':
        return ResourceWarning()
    if name == 'RuntimeWarning':
        return RuntimeWarning()
    if name == 'SyntaxWarning':
        return SyntaxWarning()
    if name == 'UnicodeWarning':
        return UnicodeWarning()
    if name == 'UserWarning':
        return UserWarning()
    assert False, name
    return BaseException()


def is_instance(e: BaseException, name: str) -> bool:
    # isinstance(e, the class that name names)
    if name == 'BaseException':
        return isinstance(e, BaseException)
    if name == 'Exception':
        return isinstance(e, Exception)
    if name == 'ArithmeticError':
        return isinstance(e, ArithmeticError)
    if name == 'ImportError':
        return isinstance(e, ImportError)
    if name == 'LookupError':
        return isinstance(e, LookupError)
    if name == 'NameError':
        return isinstance(e, NameError)
    if name == 'OSError':
        return isinstance(e, OSError)
    if name == 'ConnectionError':
        return isinstance(e, ConnectionError)
    if name == 'RuntimeError':
        return isinstance(e, RuntimeError)
    if name == 'SyntaxError':
        return isinstance(e, SyntaxError)
    if name == 'IndentationError':
        return isinstance(e, IndentationError)
    if name == 'ValueError':
        return isinstance(e, ValueError)
    if name == 'UnicodeError':
        return isinstance(e, UnicodeError)
    if name == 'Warning':
        return isinstance(e, Warning)
    assert False, name
    return False


NOT_MADE = ['BaseExceptionGroup', 'ExceptionGroup', 'UnicodeDecodeError', 'UnicodeEncodeError',
            'UnicodeTranslateError']


def test_inheritance() -> None:
    # Make sure the inheritance hierarchy matches the documentation
    inheritance_tree = EXCEPTION_HIERARCHY.splitlines()  # open(... 'exception_hierarchy.txt' ...)
    superclass_name = inheritance_tree[0].rstrip()  # inheritance_tree.readline().rstrip()
    last_exc = superclass_name  # getattr(builtins, superclass_name)
    print("base class", last_exc)
    superclasses: list[tuple[int, str]] = []  # Loop will insert base exception
    last_depth = 0
    n = 0
    for exc_line in inheritance_tree[1:]:
        exc_line = exc_line.rstrip()
        depth = exc_line.rindex('-')
        exc_name = exc_line[depth+2:]  # Slice past space
        if '(' in exc_name:  # (no platform-specific class in 3.13's file)
            assert False, exc_name
        if '[' in exc_name:
            left_bracket = exc_name.index('[')
            exc_name = exc_name[:left_bracket-1]  # cover space
        exc = exc_name  # getattr(builtins, exc_name)
        if last_depth < depth:
            superclasses.append((last_depth, last_exc))
        elif last_depth > depth:
            while superclasses[-1][0] >= depth:
                superclasses.pop()
        if exc in NOT_MADE:
            print("%s: a subclass of %s, not checked" % (exc, superclasses[-1][1]))
        else:
            check_true("issubclass(%s, %s)" % (exc, superclasses[-1][1]),
                       is_instance(make(exc), superclasses[-1][1]))
            n += 1
        last_exc = exc
        last_depth = depth
    print("test_inheritance: %d classes checked" % n)


def interface_test_driver(results: list[tuple[str, str, str]]) -> None:
    # for test_name, (given, expected) in zip(self.interface_tests, results):
    for test_name, given, expected in results:
        print(test_name, repr(given))
        assert given == expected, "%s: %s != %s" % (test_name, given, expected)


def test_interface_single_arg() -> None:
    # Make sure interface works properly when given a single argument
    arg = "spam"
    exc = Exception(arg)
    results = [("str", str(exc), str(arg)),
        ("repr", repr(exc), '%s(%r)' % (type(exc).__name__, arg))]
    interface_test_driver(results)


def test_interface_multi_arg() -> None:
    # Make sure interface correct when multiple arguments given
    arg_count = 3
    args = (0, 1, 2)  # tuple(range(arg_count))
    exc = Exception(*args)
    results = [("str", str(exc), str(args)),
            ("repr", repr(exc), type(exc).__name__ + repr(args))]
    interface_test_driver(results)


def test_interface_no_arg() -> None:
    # Make sure that with no args that interface is correct
    exc = Exception()
    results = [("str", str(exc), ''),
            ("repr", repr(exc), type(exc).__name__ + '()')]
    interface_test_driver(results)


test_inheritance()
test_interface_single_arg()
test_interface_multi_arg()
test_interface_no_arg()
