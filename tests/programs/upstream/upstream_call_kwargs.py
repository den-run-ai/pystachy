# Adapted from CPython 3.13.16 Lib/test/test_call.py: FunctionCalls.test_kwargs_order_preserved
# and test_kwargs_order_preserved_in_methods, and the Python callables of FastCallTests'
# CALLS_POSARGS and CALLS_KWARGS, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, and annotations are added where the subset needs them. Test-method classes are
# module-level classes. FastCallTests passes its rows to _testcapi's PyObject_Vectorcall() and
# PyObject_VectorcallDict(); here each Python callable of a row is called as Python spells those
# calls, func(*args) and func(*args, **kwargs), and checked against the row's expected result.
# EXCLUDED upstream cases (the error-message tests are in tests/errors/upstream/upstream_call_*.py):
# - test_kwargs_order, test_kwargs_order_preserved_in_c_functions: collections.OrderedDict, and
#   dict() with keyword arguments (not supported: a dict display is)
# - test_frames_are_popped_after_failed_calls: calls whose arguments do not fit are compile-time
#   errors here (and a list of a function, a method and [].__len__ has no one type)
# - CFunctionCallsErrorMessages (cpython_only): the C functions' messages; Pystachy rejects
#   these calls at compile time with messages of its own (input(1, 2): "input() takes exactly one
#   argument (2 given)", bug: message wording, #277; `{}.get()` with a typed dict crashes the
#   compiler: bug: IndexError in bmethod(), #274), and has no getattr(), struct, deque,
#   itertools, object() or module objects
# - FastCallTests' rows of PythonClass.class_method and .static_method (a static or class method
#   is not a value), of _testcapi's functions, test_fastcall_clearing_dict (__index__, gc,
#   compile()); TestCallingConventions*, TestPEP590, TestCAPI, TestRecursion: _testcapi
# - TestErrorMessagesSuggestions' cases with a suggestion: Pystachy's compile-time messages
#   leave out CPython 3.13's "Did you mean '...'?" (bug: no keyword suggestion; #277; the
#   cases without one are rejection fixtures), and str.split()'s keyword arguments (not
#   supported)
# - TestFunctionWithManyArgs: exec(), and `*` of a range


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def test_kwargs_order_preserved() -> None:
    # PEP 468: Preserving Keyword Argument Order
    def fn(**kw):
        return list(kw)

    check("fn(b=1, a=2, c=3)", fn(b=1, a=2, c=3), ['b', 'a', 'c'])
    check("fn(c=3, a=2, b=1)", fn(c=3, a=2, b=1), ['c', 'a', 'b'])
    # Unpacked mappings are merged in place, keeping their own order.
    check("fn(z=0, **{'x': 1, 'a': 2}, y=3)", fn(z=0, **{'x': 1, 'a': 2}, y=3),
          ['z', 'x', 'a', 'y'])
    check("fn(**{'b': 1}, **{'a': 2})", fn(**{'b': 1}, **{'a': 2}), ['b', 'a'])
    # Named parameters are removed from **kwargs without reordering
    # the rest.
    def fn2(a, c=None, **kw):
        return list(kw)

    check("fn2(d=1, a=2, b=3, c=4, e=5)", fn2(d=1, a=2, b=3, c=4, e=5), ['d', 'b', 'e'])


class C:
    def __init__(self, **kw):
        self.init_kw: list[str] = list(kw)

    def meth(self, **kw):
        return list(kw)

    @classmethod
    def cmeth(cls, **kw):
        return list(kw)

    @staticmethod
    def smeth(**kw):
        return list(kw)


def test_kwargs_order_preserved_in_methods() -> None:
    # PEP 468: Preserving Keyword Argument Order
    c = C(b=1, a=2, c=3)
    check("c.init_kw", c.init_kw, ['b', 'a', 'c'])
    check("c.meth(b=1, a=2, c=3)", c.meth(b=1, a=2, c=3), ['b', 'a', 'c'])
    check("C.cmeth(b=1, a=2, c=3)", C.cmeth(b=1, a=2, c=3), ['b', 'a', 'c'])
    check("C.smeth(b=1, a=2, c=3)", C.smeth(b=1, a=2, c=3), ['b', 'a', 'c'])


def pyfunc(arg1, arg2):
    return [arg1, arg2]


def pyfunc_noarg() -> str:
    return "noarg"


class PythonClass:
    def method(self, arg1, arg2):
        return [arg1, arg2]

    def method_noarg(self) -> str:
        return "noarg"


PYTHON_INSTANCE = PythonClass()


def test_fastcall_python_callables() -> None:
    # CALLS_POSARGS: (func, args: tuple, result)
    check("pyfunc(*(1, 2))", pyfunc(*(1, 2)), [1, 2])
    check("pyfunc_noarg(*())", pyfunc_noarg(*()), "noarg")
    check("PYTHON_INSTANCE.method(*(1, 2))", PYTHON_INSTANCE.method(*(1, 2)), [1, 2])
    check("PYTHON_INSTANCE.method_noarg(*())", PYTHON_INSTANCE.method_noarg(*()), "noarg")
    # CALLS_KWARGS: (func, args: tuple, kwargs: dict, result)
    check("pyfunc(*(1,), **{'arg2': 2})", pyfunc(*(1,), **{'arg2': 2}), [1, 2])
    check("pyfunc(*(), **{'arg1': 1, 'arg2': 2})", pyfunc(*(), **{'arg1': 1, 'arg2': 2}), [1, 2])
    check("PYTHON_INSTANCE.method(*(1,), **{'arg2': 2})",
          PYTHON_INSTANCE.method(*(1,), **{'arg2': 2}), [1, 2])
    check("PYTHON_INSTANCE.method(*(), **{'arg1': 1, 'arg2': 2})",
          PYTHON_INSTANCE.method(*(), **{'arg1': 1, 'arg2': 2}), [1, 2])
    # the bound methods as values, as the rows hold them
    method = PYTHON_INSTANCE.method
    method_noarg = PYTHON_INSTANCE.method_noarg
    check("method(*(1, 2))", method(*(1, 2)), [1, 2])
    check("method_noarg(*())", method_noarg(*()), "noarg")
    check("method(*(1,), **{'arg2': 2})", method(*(1,), **{'arg2': 2}), [1, 2])
    check("method(*(), **{'arg1': 1, 'arg2': 2})", method(*(), **{'arg1': 1, 'arg2': 2}), [1, 2])


test_kwargs_order_preserved()
test_kwargs_order_preserved_in_methods()
test_fastcall_python_callables()
