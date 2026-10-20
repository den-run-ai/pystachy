# Adapted from CPython 3.13.16 Lib/test/test_exceptions.py, class ExceptionTests:
# test_exception_cleanup_names, test_exception_cleanup_names2,
# test_raise_does_not_create_context_chain_cycle, test_context_of_exception_in_try_and_finally,
# test_context_of_exception_in_except_and_finally, test_context_of_exception_in_else_and_finally
# and test_memory_error_subclasses, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertIs(a, b) of exceptions prints a and
# asserts a is b, assertIsInstance(a, C) prints the isinstance() test and asserts it,
# assertRaises a try statement that prints the exception. Test-method classes are module classes.
# EXCLUDED upstream cases (see also tests/programs/upstream/upstream_exceptions_raising.py):
# - test_exception_cleanup_names' and _names2's self.assertNotIn('e', locals()) (no locals())
# - the __context__ assertions of test_raise_does_not_create_context_chain_cycle and the
#   test_context_of_exception_* methods (an exception's attributes are not supported; their
#   flows and the identity of the exception caught are kept), and
#   test_no_hang_on_context_chain_cycle1, test_no_hang_on_context_chain_cycle2 and
#   test_no_hang_on_context_chain_cycle3 (they assign __context__)
# - test_memory_error_subclasses' gc_collect() (no gc module)
# - test_exception_target_in_nested_scope (a closure that reads the name an except clause binds
#   is rejected at compile time, and its `something` is unbound)
# - testExceptionCleanupState (weakref, gc, and a with statement over an object: `with` takes
#   open()'s files only), test_3114 (__del__), test_unraisable (__del__,
#   catch_unraisable_exception), test_unhandled (sys.__excepthook__, captured_stderr)
# - test_generator_leaking, test_generator_leaking2, test_generator_leaking3,
#   test_generator_leaking4, test_generator_doesnt_retain_old_exc,
#   test_generator_finalizing_and_sys_exception, test_generator_throw_cleanup_exc_state,
#   test_generator_close_cleanup_exc_state, test_generator_del_cleanup_exc_state,
#   test_generator_next_cleanup_exc_state, test_generator_send_cleanup_exc_state,
#   test_yield_in_nested_try_excepts, test_generator_doesnt_retain_old_exc2 and
#   test_raise_in_generator (generator functions, sys.exception())
# - test_unicode_change_attributes, test_unicode_errors_no_object and
#   test_unicode_error_str_does_not_crash (the attributes of UnicodeEncodeError and
#   UnicodeDecodeError, which they set, klass.__new__ and UnicodeTranslateError() are not
#   supported)
# - test_oserror_reinit_leak (a subclass of OSError that assigns strerror, filename and
#   filename2, the base's own attributes: rejected at compile time), test_errno_ENOTDIR
#   (os.listdir() and e.errno are not supported), test_assert_shadowing (`AssertionError =
#   TypeError`: a builtin exception class is no value here)
# - NameErrorTests: test_name_error_has_name (the read of an unbound name is a compile-time
#   error with CPython's message, tests/errors/upstream/upstream_exceptions_name_error.py; exc.name is not
#   supported), test_issue45826 and test_issue45826_focused (unittest's failureException,
#   sys.__excepthook__, with_traceback()), test_gh_111654 (a class inside a function)
# - AttributeErrorTests: test_attributes (AttributeError's name and obj; object()),
#   test_getattr_has_name_and_obj and test_getattr_has_name_and_obj_for_method (a read of an
#   attribute that a class does not have is a compile-time error, also
#   object.__getattribute__())
# - ImportErrorTests: test_attributes' TypeErrors are compile-time errors with CPython's message
#   (tests/errors/upstream/upstream_exceptions_importerror_*.py), its name and path are not supported, nor
#   test_reset_attributes' (msg, __init__()), test_non_str_argument (bytes) and
#   test_copy_pickle (pickle, copy)
# - AssertionErrorTests (test_assertion_error_location, test_multiline_not_highlighted: the
#   source lines and carets of a traceback, which Pystachy does not print; the last line of
#   an uncaught AssertionError is CPython's)
# - SyntaxErrorTests: test_non_utf8 is tests/errors/upstream/upstream_exceptions_syntax_non_utf8.py;
#   test_range_of_offsets, test_subclass, test_attributes_new_constructor,
#   test_attributes_old_constructor, test_incorrect_constructor and
#   test_syntax_error_memory_leak (SyntaxError() of a location tuple, a subclass of SyntaxError,
#   sys.__excepthook__ and SyntaxError's attributes are not supported), test_encodings
#   (cp437 and ascii source declarations, subprocesses), test_string_source (compile()) and
#   test_file_source (a traceback's source line and carets, BOM and Latin-1 sources)
# - TestInvalidExceptionMatcher.test_except_star_invalid_exception_type (`except 42` and `except
#   (ValueError, 42)`: compile-time errors worded "an except clause needs exception classes: a
#   name, or a tuple of names", where CPython says "catching classes that do not inherit from
#   BaseException is not allowed")
# - PEP626Tests (test_lineno_after_raise_simple, test_lineno_after_raise_in_except,
#   test_lineno_after_other_except, test_lineno_in_named_except, test_lineno_in_try,
#   test_lineno_in_finally_normal, test_lineno_in_finally_except, test_lineno_after_with,
#   test_missing_lineno_shows_as_none, test_lineno_after_raise_in_with_exit): __traceback__ and
#   frames, with statements over objects, f.__code__


def check_is(label: str, got, expected) -> None:
    # assertIs(got, expected) of exceptions
    print(label, repr(got))
    assert got is expected, label


def check_true(label: str, got: bool) -> None:
    print(label, repr(got))
    assert got, label


def test_exception_cleanup_names() -> None:
    # Make sure the local variable bound to the exception instance by
    # an "except" statement is only visible inside the except block.
    try:
        raise Exception()
    except Exception as e:
        check_true("isinstance(e, Exception)", isinstance(e, Exception))
    try:
        e
    except UnboundLocalError as u:
        print("e: UnboundLocalError:", u)
    else:
        assert False, "expected UnboundLocalError"


def test_exception_cleanup_names2() -> None:
    # Make sure the cleanup doesn't break if the variable is explicitly deleted.
    try:
        raise Exception()
    except Exception as e:
        check_true("isinstance(e, Exception)", isinstance(e, Exception))
        del e
    try:
        e
    except UnboundLocalError as u:
        print("e: UnboundLocalError:", u)
    else:
        assert False, "expected UnboundLocalError"


class A(Exception):
    pass
class B(Exception):
    pass
class C(Exception):
    pass


def test_raise_does_not_create_context_chain_cycle() -> None:
    # Create a context chain:
    # C -> B -> A
    # Then raise A in context of C.
    try:
        try:
            raise A
        except A as a_:
            a = a_
            try:
                raise B
            except B as b_:
                b = b_
                try:
                    raise C
                except C as c_:
                    c = c_
                    check_true("isinstance(a, A)", isinstance(a, A))
                    check_true("isinstance(b, B)", isinstance(b, B))
                    check_true("isinstance(c, C)", isinstance(c, C))
                    raise a
    except A as e:
        exc = e

    # Expect A -> C -> B, without cycle
    check_is("exc is a", exc, a)


def test_context_of_exception_in_try_and_finally() -> None:
    try:
        try:
            te = TypeError(1)
            raise te
        finally:
            ve = ValueError(2)
            raise ve
    except Exception as e:
        exc = e

    check_is("exc is ve", exc, ve)


def test_context_of_exception_in_except_and_finally() -> None:
    try:
        try:
            te = TypeError(1)
            raise te
        except:
            ve = ValueError(2)
            raise ve
        finally:
            oe = OSError(3)
            raise oe
    except Exception as e:
        exc = e

    check_is("exc is oe", exc, oe)


def test_context_of_exception_in_else_and_finally() -> None:
    try:
        try:
            pass
        except:
            pass
        else:
            ve = ValueError(1)
            raise ve
        finally:
            oe = OSError(2)
            raise oe
    except Exception as e:
        exc = e

    check_is("exc is oe", exc, oe)


class TestException(MemoryError):
    pass


def test_memory_error_subclasses() -> None:
    # bpo-41654: MemoryError instances use a freelist of objects that are
    # linked using the 'dict' attribute when they are inactive/dead.
    # Subclasses of MemoryError should not participate in the freelist
    # schema. This test creates a MemoryError object and keeps it alive
    # (therefore advancing the freelist) and then it creates and destroys a
    # subclass object. Finally, it checks that creating a new MemoryError
    # succeeds, proving that the freelist is not corrupted.

    try:
        raise MemoryError
    except MemoryError as exc:
        inst = exc

    try:
        raise TestException
    except Exception:
        pass

    for _ in range(10):
        try:
            raise MemoryError
        except MemoryError as exc:
            pass

        # gc_collect()
    print("inst:", repr(inst))


test_exception_cleanup_names()
test_exception_cleanup_names2()
test_raise_does_not_create_context_chain_cycle()
test_context_of_exception_in_try_and_finally()
test_context_of_exception_in_except_and_finally()
test_context_of_exception_in_else_and_finally()
test_memory_error_subclasses()
