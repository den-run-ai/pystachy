# Adapted from CPython 3.13.16 Lib/test/test_decorators.py, class TestDecorators: test_single,
# test_dotted, test_argforms, test_memoize, test_errors (its raising decorator), test_order and
# test_eval_order, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, and annotations are added where the subset needs them. Functions have no attributes
# here, so where upstream's decorators set one (func.__dict__['author'] = name,
# setattr(func, 'dbval', ...)), they return an object (Noted) that holds the function and that
# attribute and calls the function. dict(k=v) is written as the equal display {'k': v}.
# test_eval_order: NameLookupTracer's attributes are methods (upstream's __getattr__ is not
# supported, nor @property), so step 1, the maker's name lookup, logs nothing ('evalname%d' is
# dropped from the expected list) and c1.arg is a call; map(NameLookupTracer, ...) is a
# comprehension (classes are not values). test_eval_order_name_first, Pystachy's own, shows step 1
# another way: an argument that rebinds the maker's name does not change the maker called.
# The memoize and countcalls decorators leave out `call.__name__ = ...` (no function attributes).
# EXCLUDED upstream cases:
# - test_staticmethod, test_classmethod: staticmethod() and classmethod() objects as values, their
#   __func__ and __wrapped__ (not supported)
# - test_dbcheck: compile() and eval()
# - test_double, TestClassDecorators (test_simple, test_double, test_order): attributes of
#   functions and classes, and class decorators
# - test_bound_function_inside_classmethod: classmethod() of a bound method as a class attribute
# - test_argforms' f1: `**kwds` of a dict variable (only a function's own **kwargs is forwarded)
# - test_argforms' f3 copies its empty **kwargs with `if kwds else {}`, as dict() of an empty
#   **kwargs is rejected at compile time even where an annotation types it (bug: dict(kwargs) of
#   an empty **kwargs, "cannot infer the type of an empty dict"; existing issue #240, which
#   reports kw.items() of it)
# - memoize's `saved = {}` is annotated: a closure cannot capture an empty container that only
#   the closure fills (existing issue #246)
# - test_memoize: double.__name__ (the wrapper's name here: assigning `__name__` to a function is
#   not supported), and the unhashable list argument (a list as a dict key is rejected at compile
#   time, where CPython raises TypeError)
# - test_errors: the SyntaxErrors are tests/errors/upstream/upstream_decorators_syntax_*.py, the undefined
#   decorator tests/errors/upstream/upstream_decorators_undef.py; decorators that are not a dotted name or
#   a call of one (`@1.+2j`, `@[1, 2][-1]`, `@(1, 2)`, `@True`, `@...`, `@None`; PEP 614) and a
#   call or an attribute of None (`@nullval`, `@nullval.attr`) are rejected at compile time with
#   messages of their own, where CPython raises TypeError and AttributeError; `assert f() is None`
#   after the raising decorator, which CPython never reaches, calls None (a compile-time error)
# - test_expressions: compile() of PEP 614 decorator expressions
from typing import Callable


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


class Noted:
    # what the decorated function becomes: the function and the attribute upstream sets on it
    def __init__(self, func, note):
        self.func = func
        self.note = note

    def __call__(self):
        return self.func()


class MiscDecorators (object):
    @staticmethod
    def author(name):
        def decorate(func):
            return Noted(func, name)  # upstream: func.__dict__['author'] = name; return func
        return decorate


def countcalls(counts):
    "Decorator to count calls to a function"
    def decorate(func):
        func_name = func.__name__
        counts[func_name] = 0
        def call(*args, **kwds):
            counts[func_name] += 1
            return func(*args, **kwds)
        return call
    return decorate


def memoize(func):
    saved: dict[tuple[int], int] = {}
    def call(*args):
        try:
            return saved[args]
        except KeyError:
            res = func(*args)
            saved[args] = res
            return res
        except TypeError:
            # Unhashable argument
            return func(*args)
    return call


class C(object):
    @staticmethod
    def foo() -> int: return 42


def test_single() -> None:
    check("C.foo()", C.foo(), 42)
    check("C().foo()", C().foo(), 42)


def test_dotted() -> None:
    decorators = MiscDecorators()
    @decorators.author('Cleese')
    def foo(): return 42
    check("foo()", foo(), 42)
    check("foo.author", foo.note, 'Cleese')


def test_argforms() -> None:
    # A few tests of argument passing, as we use restricted form
    # of expressions for decorators.

    def noteargs(*args, **kwds):
        def decorate(func):
            # (kwds as a dict; dict() of an empty **kwargs is rejected: see the header)
            kw: dict[str, str] = dict(kwds) if kwds else {}
            return Noted(func, (args, kw))  # upstream: setattr(func, 'dbval', (args, kwds))
        return decorate

    @noteargs('terry', 'gilliam', eric='idle', john='cleese')
    def f2(): return 84
    check("f2()", f2(), 84)
    check("f2.dbval", f2.note, (('terry', 'gilliam'),
                                 {'eric': 'idle', 'john': 'cleese'}))  # dict(eric='idle', john='cleese')

    @noteargs(1, 2,)
    def f3(): pass
    check("f3()", f3(), None)
    empty: dict[str, str] = {}
    check("f3.dbval", f3.note, ((1, 2), empty))


def test_memoize() -> None:
    counts: dict[str, int] = {}

    @memoize
    @countcalls(counts)
    def double(x):
        return x * 2

    check("counts", counts, {'double': 0})  # dict(double=0)

    # Only the first call with a given argument bumps the call count:
    #
    check("double(2)", double(2), 4)
    check("counts['double']", counts['double'], 1)
    check("double(2)", double(2), 4)
    check("counts['double']", counts['double'], 1)
    check("double(3)", double(3), 6)
    check("counts['double']", counts['double'], 2)


def unimp(func):
    raise NotImplementedError


def define_unimp() -> None:
    @unimp
    def f(): pass
    # (upstream's `assert f() is None` is not reached; f, unimp's result, is None here, and
    # calling it a compile-time error)


def test_errors() -> None:
    # ("unimp", NotImplementedError): the decorator raises when the def statement runs
    try:
        define_unimp()
    except NotImplementedError as e:
        print("NotImplementedError", repr(e))
    else:
        assert False, "expected NotImplementedError"


def test_order() -> None:
    # Test that decorators are applied in the proper order to the function
    # they are decorating.
    def callnum(num):
        """Decorator factory that returns a decorator that replaces the
        passed-in function with one that returns the value of 'num'"""
        def deco(func):
            return lambda: num
        return deco
    @callnum(2)
    @callnum(1)
    def foo(): return 42
    check("foo()", foo(), 2)


# test_eval_order
actions: list[str] = []


def make_decorator(tag: str) -> Callable[[Callable[[], int]], Callable[[], int]]:
    actions.append('makedec' + tag)
    def decorate(func: Callable[[], int]) -> Callable[[], int]:
        actions.append('calldec' + tag)
        return func
    return decorate


class NameLookupTracer (object):
    def __init__(self, index: int) -> None:
        self.index = index

    # upstream: __getattr__(self, fname), which logs 'evalname%d' for 'make_decorator' (step 1)
    # and 'evalargs%d' for 'arg'; here make_decorator is a method, and arg() logs as arg did
    def make_decorator(self, tag: str) -> Callable[[Callable[[], int]], Callable[[], int]]:
        return make_decorator(tag)

    def arg(self) -> str:
        opname, res = ('evalargs', str(self.index))
        actions.append('%s%d' % (opname, self.index))
        return res


def test_eval_order() -> None:
    # Evaluating a decorated function involves four steps for each
    # decorator-maker (the function that returns a decorator):
    #
    #    1: Evaluate the decorator-maker name
    #    2: Evaluate the decorator-maker arguments (if any)
    #    3: Call the decorator-maker to make a decorator
    #    4: Call the decorator
    #
    # When there are multiple decorators, these steps should be
    # performed in the above order for each decorator, but we should
    # iterate through the decorators in the reverse of the order they
    # appear in the source.
    global actions

    c1, c2, c3 = [NameLookupTracer(i) for i in [ 1, 2, 3 ]]  # map(NameLookupTracer, [ 1, 2, 3 ])

    # (upstream's list, without the 'evalname' entries of step 1)
    expected_actions = [ 'evalargs1', 'makedec1',
                         'evalargs2', 'makedec2',
                         'evalargs3', 'makedec3',
                         'calldec3', 'calldec2', 'calldec1' ]

    actions = []
    @c1.make_decorator(c1.arg())
    @c2.make_decorator(c2.arg())
    @c3.make_decorator(c3.arg())
    def foo() -> int: return 42
    check("foo()", foo(), 42)

    check("actions", actions, expected_actions)

    # Test the equivalence claim in chapter 7 of the reference manual.
    #
    actions = []
    def bar() -> int: return 42
    bar2 = c1.make_decorator(c1.arg())(c2.make_decorator(c2.arg())(c3.make_decorator(c3.arg())(bar)))
    check("bar()", bar2(), 42)
    check("actions", actions, expected_actions)


# Extension standing in for step 1: the decorator-maker's name is evaluated before its arguments,
# so an argument that rebinds the name does not change the maker called.
def other_maker(tag: str) -> Callable[[Callable[[], int]], Callable[[], int]]:
    actions.append('othermaker' + tag)
    return make_decorator(tag)


maker: Callable[[str], Callable[[Callable[[], int]], Callable[[], int]]] = make_decorator


def rebinding_arg(tag: str) -> str:
    global maker
    actions.append('evalargs' + tag)
    maker = other_maker
    return tag


def test_eval_order_name_first() -> None:
    global actions
    actions = []
    @maker(rebinding_arg('1'))
    @maker(rebinding_arg('2'))
    def baz() -> int: return 7
    check("baz()", baz(), 7)
    check("actions", actions, ['evalargs1', 'makedec1', 'evalargs2', 'othermaker2', 'makedec2',
                               'calldec2', 'calldec1'])


test_single()
test_dotted()
test_argforms()
test_memoize()
test_errors()
test_order()
test_eval_order()
test_eval_order_name_first()
