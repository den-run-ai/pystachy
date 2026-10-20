# Adapted from CPython 3.13.16 Lib/test/test_generators.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91: GeneratorTest.test_send_non_none_to_new_gen;
# ExceptionTest's test_except_throw, test_except_next, test_except_gen_except,
# test_nested_gen_except_loop, test_except_throw_exception_context, test_stopiteration_error,
# test_tutorial_stopiteration; GeneratorCloseTest's test_close_no_return_value,
# test_close_not_catching_exit, test_close_not_started, test_close_exhausted, test_close_closed,
# test_close_raises; GeneratorThrowTest.test_throw_after_none_exc_type; and the coroutine_tests
# doctests of send(), throw() and close().
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name (a doctest, a function named for what it
# checks); assertEqual(a, b), assertIsNone(x), assertIsInstance(x, C) and assertRaises print what
# they check, so the recording holds the values. Generator functions are annotated
# (Iterator[T], or Generator[Y, S, R] where they take send()), and self.assert... inside a
# generator prints. close() is called as a statement: assertIsNone(gen.close()) is gen.close()
# and a print. The doctests' coroutine with count += yield takes the value sent in a variable
# first (a yield's value is S | None: next() sends None), and "GeneratorExit is not caught by
# except Exception" closes the generator where the doctest deletes it.
# EXCLUDED upstream cases:
# - close()'s value (test_close_return_value and the 0 the others compare): rejected, "the value
#   of generator.close() is not supported"; the generator's static type holds no return type
# - exc.__context__ and __traceback__ (test_except_throw's, test_except_throw_exception_context's
#   and the doctest that counts traceback levels): exception attributes are rejected
# - StopIteration.value (test_return_tuple, test_return_stopiteration): rejected
#   (tests/deviations/gen_stop_value.py)
# - throw(type, value[, tb]) (test_gen_3_arg_deprecation_warning, the doctests' two- and
#   three-argument calls and throw(*sys.exc_info())): deprecated and rejected
#   (tests/errors/generators/gen_throw_three.py); throw() of a str, an int, list or a class whose __new__
#   returns no instance (test_except_throw_bad_exception): rejected as the program compiles
# - finalization by del and gc_collect(), and the ill-behaved generator's unraisable report:
#   a dropped generator is not closed (tests/deviations/gen_finalization.py)
# - the doctests' syntax errors, type(f()) of yields in lambdas and generator expressions, and
#   d[(yield "a")] = d[(yield "b")] = 27 (a yield's value S | None as an index is rejected)
# - the rest of the module (tutorial, PEP 255, email, fun, conjoin, weakref and refleak doctests,
#   gi_frame, gi_code, f_locals, names, copy, pickle, stack traces): no frames or introspection
import sys
from collections.abc import Generator, Iterator


def test_send_non_none_to_new_gen() -> None:
    def f() -> Generator[int, int, None]:
        yield 1
    g = f()
    try:
        g.send(0)
    except TypeError as e:
        print("TypeError", e)
    print(next(g))


def test_except_throw() -> None:
    def store_raise_exc_generator() -> Iterator[None]:
        try:
            print("assertIsNone", sys.exception())
            yield
        except Exception as exc:
            # exception raised by gen.throw(exc)
            print("assertIsInstance", isinstance(sys.exception(), ValueError))
            yield

            # ensure that the exception is not lost
            print("assertIsInstance", isinstance(sys.exception(), ValueError))
            yield

            # we should be able to raise back the ValueError
            raise

    make = store_raise_exc_generator()
    next(make)

    try:
        raise ValueError()
    except Exception as exc:
        try:
            make.throw(exc)
        except Exception:
            pass

    next(make)
    try:
        next(make)
    except ValueError as e:
        print("assertRaises ValueError", repr(e))

    print("assertIsNone", sys.exception())


def test_except_next() -> None:
    def gen() -> Iterator[str]:
        print("assertIsInstance", isinstance(sys.exception(), ValueError))
        yield "done"

    g = gen()
    try:
        raise ValueError
    except Exception:
        print("assertEqual", next(g), "done")
    print("assertIsNone", sys.exception())


def test_except_gen_except() -> None:
    def gen() -> Iterator[str | None]:
        try:
            print("assertIsNone", sys.exception())
            yield None
            # we are called from "except ValueError:", TypeError must
            # inherit ValueError in its context
            raise TypeError()
        except TypeError as exc:
            print("assertIsInstance", isinstance(sys.exception(), TypeError))
        # here we are still called from the "except ValueError:"
        print("assertIsInstance", isinstance(sys.exception(), ValueError))
        yield None
        print("assertIsNone", sys.exception())
        yield "done"

    g = gen()
    next(g)
    try:
        raise ValueError
    except Exception:
        next(g)

    print("assertEqual", next(g), "done")
    print("assertIsNone", sys.exception())


def test_nested_gen_except_loop() -> None:
    def gen() -> Iterator[str]:
        for i in range(100):
            if not isinstance(sys.exception(), TypeError):
                print("assertIsInstance failed", i)
            yield "doing"

    def outer() -> Iterator[str]:
        try:
            raise TypeError
        except:
            for x in gen():
                yield x

    n = 0
    try:
        raise ValueError
    except Exception:
        for x in outer():
            if x == "doing":
                n += 1
    print("assertEqual doing", n)
    print("assertEqual", sys.exception(), None)


def test_except_throw_exception_context() -> None:
    def gen() -> Iterator[str | None]:
        try:
            try:
                print("assertIsNone", sys.exception())
                yield None
            except ValueError:
                # we are called from "except ValueError:"
                print("assertIsInstance", isinstance(sys.exception(), ValueError))
                raise TypeError()
        except Exception as exc:
            print("assertIsInstance", isinstance(sys.exception(), TypeError))
        # we are still called from "except ValueError:"
        print("assertIsInstance", isinstance(sys.exception(), ValueError))
        yield None
        print("assertIsNone", sys.exception())
        yield "done"

    g = gen()
    next(g)
    try:
        raise ValueError
    except Exception as exc:
        g.throw(exc)

    print("assertEqual", next(g), "done")
    print("assertIsNone", sys.exception())


def test_stopiteration_error() -> None:
    # See also PEP 479.

    def gen() -> Iterator[None]:
        raise StopIteration
        yield

    try:
        next(gen())
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)


def test_tutorial_stopiteration() -> None:
    # Raise StopIteration" stops the generator too:

    def f() -> Iterator[int]:
        yield 1
        raise StopIteration
        yield 2 # never reached

    g = f()
    print("assertEqual", next(g), 1)

    try:
        next(g)
    except RuntimeError as e:
        print("assertRaisesRegex RuntimeError", e)


def test_close_no_return_value() -> None:
    def f() -> Iterator[None]:
        yield

    gen = f()
    gen.send(None)
    gen.close()
    print("closed")


def test_close_not_catching_exit() -> None:
    def f() -> Generator[None, None, int]:
        yield
        # close() raises GeneratorExit here, which isn't caught and
        # therefore propagates -- no return value
        return 0

    gen = f()
    gen.send(None)
    gen.close()
    print("closed")


def test_close_not_started() -> None:
    def f() -> Generator[None, None, int]:
        try:
            yield
        except GeneratorExit:
            print("not reached")
            return 0
        return 1

    gen = f()
    gen.close()
    print("closed")


def test_close_exhausted() -> None:
    def f() -> Generator[None, None, int]:
        try:
            yield
        except GeneratorExit:
            print("not reached")
            return 0
        return 1

    gen = f()
    next(gen)
    try:
        next(gen)
    except StopIteration:
        print("assertRaises StopIteration")
    gen.close()
    print("closed")


def test_close_closed() -> None:
    def f() -> Generator[None, None, int]:
        try:
            yield
        except GeneratorExit:
            print("caught GeneratorExit")
            return 0
        return 1

    gen = f()
    gen.send(None)
    gen.close()
    gen.close()
    print("closed twice")


def test_close_raises() -> None:
    def f() -> Iterator[None]:
        try:
            yield
        except GeneratorExit:
            pass
        raise RuntimeError

    gen = f()
    gen.send(None)
    try:
        gen.close()
    except RuntimeError as e:
        print("assertRaises RuntimeError", repr(e))


def test_throw_after_none_exc_type() -> None:
    def g() -> Iterator[None]:
        try:
            raise KeyError
        except KeyError:
            pass

        try:
            yield
        except Exception:
            raise RuntimeError

    gen = g()
    gen.send(None)
    try:
        gen.throw(ValueError)
    except RuntimeError as e:
        print("assertRaises RuntimeError", repr(e))


def coroutine_send() -> None:
    # Sending a value into a started generator:
    def f() -> Generator[int, int, None]:
        print((yield 1))
        yield 2
    g = f()
    print(next(g))
    print(g.send(42))

    # Sending a value into a new generator produces a TypeError:
    try:
        f().send(5)
    except TypeError as e:
        print("TypeError:", e)

    # Yield by itself yields None:
    def f2() -> Iterator[None]:
        yield
    print(list(f2()))


def coroutine_augmented() -> None:
    # A yield expression with augmented assignment.
    def coroutine(seq: list[int]) -> Generator[None, int, None]:
        count = 0
        while count < 200:
            v = yield
            if v is not None:
                count += v
            seq.append(count)
    seq: list[int] = []
    c = coroutine(seq)
    next(c)
    print(seq)
    c.send(10)
    print(seq)
    c.send(10)
    print(seq)
    c.send(10)
    print(seq)


def coroutine_throw() -> None:
    # Now check some throw() conditions:
    def f() -> Generator[None, int, None]:
        while True:
            try:
                print((yield))
            except ValueError as v:
                print("caught ValueError (%s)" % (v))
    g = f()
    next(g)
    g.throw(ValueError)  # type only
    g.throw(ValueError("xyz"))  # value only
    g.send(1)
    try:
        g.throw(TypeError)  # terminate the generator
    except TypeError as e:
        print("TypeError", repr(e))
    try:
        g.send(2)
    except StopIteration as e:
        print("StopIteration", repr(e))
    try:
        g.throw(ValueError(6))  # throw on closed generator
    except ValueError as e:
        print("ValueError:", e)
    try:
        f().throw(ValueError(7))  # throw on just-opened generator
    except ValueError as e:
        print("ValueError:", e)


def coroutine_close() -> None:
    # Now let's try closing a generator:
    def f() -> Iterator[None]:
        try:
            yield
        except GeneratorExit:
            print("exiting")

    g = f()
    next(g)
    g.close()
    g.close()  # should be no-op now

    f().close()  # close on just-opened generator should be fine

    def f2() -> Iterator[None]:
        yield  # an even simpler generator
    f2().close()  # close before opening
    g = f2()
    next(g)
    g.close()  # close normally

    # GeneratorExit is not caught by except Exception:
    def f3() -> Iterator[None]:
        try:
            yield
        except Exception:
            print('except')
        finally:
            print('finally')

    g = f3()
    next(g)
    g.close()

    # Now let's try some ill-behaved generators:
    def f4() -> Iterator[str | None]:
        try:
            yield None
        except GeneratorExit:
            yield "foo!"
    g4 = f4()
    next(g4)
    try:
        g4.close()
    except RuntimeError as e:
        print("RuntimeError:", e)
    g4.close()

    # And errors thrown during closing should propagate:
    def f5() -> Iterator[None]:
        try:
            yield
        except GeneratorExit:
            raise TypeError("fie!")
    g = f5()
    next(g)
    try:
        g.close()
    except TypeError as e:
        print("TypeError:", e)


test_send_non_none_to_new_gen()
test_except_throw()
test_except_next()
test_except_gen_except()
test_nested_gen_except_loop()
test_except_throw_exception_context()
test_stopiteration_error()
test_tutorial_stopiteration()
test_close_no_return_value()
test_close_not_catching_exit()
test_close_not_started()
test_close_exhausted()
test_close_closed()
test_close_raises()
test_throw_after_none_exc_type()
coroutine_send()
coroutine_augmented()
coroutine_throw()
coroutine_close()
