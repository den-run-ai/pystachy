"""Experimental, CPython-hosted specialization of small unannotated numeric kernels.

This is an opt-in function-entry cache, not a compiler for arbitrary Python. The
original function handles unsupported inputs and every failed specialization.
"""

from __future__ import annotations

import ast
import copy
import functools
import importlib.util
import inspect
import marshal
import math
from pathlib import Path
import platform
import subprocess
import sys
import sysconfig
import tempfile
import textwrap
import threading
import time
from types import CodeType, FunctionType, MethodType
from typing import Callable, Sequence
import uuid


_RANGE = range
_I64_MIN, _I64_MAX = -(1 << 63), (1 << 63) - 1
_NODES = (
    ast.FunctionDef, ast.arguments, ast.arg, ast.Assign, ast.AugAssign,
    ast.If, ast.For, ast.While, ast.Break, ast.Continue, ast.Return, ast.Pass,
    ast.Expr, ast.Name, ast.Load, ast.Store, ast.Constant, ast.BinOp,
    ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp, ast.Call,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
    ast.UAdd, ast.USub, ast.Not, ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
)


def _always_returns(body: list[ast.stmt]) -> bool:
    """Reject fallthrough: a typed native function cannot return implicit None."""
    for statement in body:
        if isinstance(statement, ast.Return):
            return True
        if isinstance(statement, ast.If) and _always_returns(statement.body) and _always_returns(statement.orelse):
            return True
    return False


def _source(function: FunctionType) -> tuple[ast.FunctionDef, bool]:
    if function.__closure__ or function.__code__.co_freevars:
        raise ValueError("closures are outside the prototype")
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError("source must contain one ordinary function")
    node = tree.body[0]
    if node.name != function.__code__.co_name:
        raise ValueError("source does not match the function's code")
    node.decorator_list = []

    # Reading the file alone is insufficient: it may have changed since import,
    # or __code__ may have been replaced. Compile without executing any source.
    compiled = compile(tree, function.__code__.co_filename, "exec", dont_inherit=True)
    codes = [value for value in compiled.co_consts if isinstance(value, CodeType)]
    if len(codes) != 1:
        raise ValueError("source does not identify one function")
    actual, expected = function.__code__, codes[0]
    fields = ("co_code", "co_names", "co_varnames", "co_exceptiontable", "co_argcount",
              "co_posonlyargcount", "co_kwonlyargcount", "co_freevars", "co_cellvars")
    if any(getattr(actual, field) != getattr(expected, field) for field in fields):
        raise ValueError("source does not match the function's code")
    # Numeric equality accepts changed literals: 1 == 1.0 == True and
    # -0.0 == 0.0. Their types and floating representations matter here.
    if marshal.dumps(actual.co_consts) != marshal.dumps(expected.co_consts):
        raise ValueError("source does not match the function's constants")
    execution_flags = inspect.CO_GENERATOR | inspect.CO_COROUTINE | inspect.CO_ASYNC_GENERATOR | inspect.CO_VARARGS | inspect.CO_VARKEYWORDS
    if actual.co_flags & execution_flags != expected.co_flags & execution_flags:
        raise ValueError("source does not match the function's execution flags")

    args = node.args
    if args.defaults or args.kw_defaults or args.vararg or args.kwarg or args.kwonlyargs:
        raise ValueError("defaults, keyword-only and variadic parameters are outside the prototype")
    # Annotations are metadata in CPython. The specialized copy learns them from
    # exact argument types, rather than trusting or evaluating user annotations.
    for arg in args.posonlyargs + args.args:
        arg.annotation = None
    node.returns = None
    local_names = {arg.arg for arg in args.posonlyargs + args.args}
    local_names.update(child.id for child in ast.walk(node) if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store))
    range_calls = {id(child.iter) for child in ast.walk(node) if isinstance(child, ast.For)}
    docstring = node.body[0] if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str) else None
    uses_range = False
    for child in ast.walk(node):
        if not isinstance(child, _NODES):
            raise ValueError(f"{type(child).__name__} is outside the numeric kernel subset")
        if isinstance(child, ast.FunctionDef) and child is not node:
            raise ValueError("nested functions are outside the prototype")
        if isinstance(child, ast.Constant):
            if docstring is not None and child is docstring.value:
                continue
            if type(child.value) not in (int, float, bool):
                raise ValueError("only numeric constants are supported")
            if type(child.value) is int and not _I64_MIN <= child.value <= _I64_MAX:
                raise ValueError("integer constants must fit signed 64 bits")
            if type(child.value) is float and not math.isfinite(child.value):
                raise ValueError("float constants must be finite")
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load) and child.id not in local_names and child.id != "range":
            raise ValueError(f"global name {child.id!r} is outside the prototype")
        if isinstance(child, ast.Assign) and any(not isinstance(target, ast.Name) for target in child.targets):
            raise ValueError("assignment targets must be local names")
        if isinstance(child, ast.AugAssign) and not isinstance(child.target, ast.Name):
            raise ValueError("assignment targets must be local names")
        if isinstance(child, ast.For) and not isinstance(child.target, ast.Name):
            raise ValueError("loop targets must be local names")
        if isinstance(child, ast.Call):
            if id(child) not in range_calls or not isinstance(child.func, ast.Name) or child.func.id != "range" or "range" in local_names or child.keywords or not 1 <= len(child.args) <= 3:
                raise ValueError("only range(...) directly in a for loop is supported")
            uses_range = True
        if isinstance(child, ast.Name) and child.id == "range" and isinstance(child.ctx, ast.Load) and not any(isinstance(call, ast.Call) and call.func is child for call in ast.walk(node)):
            raise ValueError("range may only be called by a for loop")
    if not _always_returns(node.body):
        raise ValueError("every path must end with an explicit numeric return")
    return node, uses_range


def _compile_variant(source: str, compiler: Sequence[str], directory: Path, name: str) -> Callable:
    """The backend hook; tests can replace it without replacing dispatch guards."""
    program = directory / f"{name}.py"
    extension = directory / f"{name}.abi3.so"
    program.write_text(source, encoding="utf-8")
    result = subprocess.run([*compiler, "ext", str(program), "-o", str(extension)], capture_output=True, text=True, timeout=60, check=False)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or f"compiler exited {result.returncode}")[-2000:])
    spec = importlib.util.spec_from_file_location(name, extension)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load the compiled extension")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module.kernel


class _Adaptive:
    def __init__(self, function: FunctionType, warmup: int, max_variants: int, compiler: Sequence[str] | None):
        self._function = function
        self._code = function.__code__
        self._owner = threading.get_ident()
        self._warmup = warmup
        self._limit = max_variants
        self._compiler = tuple(compiler) if compiler is not None else (sys.executable, str(Path(__file__).resolve().parents[1] / "pystachy.py"))
        self._profiles: dict[tuple[type, ...], int] = {}
        self._warmups: dict[tuple[type, ...], int] = {}
        self._variants: dict[tuple[type, ...], Callable] = {}
        self._attempted: set[tuple[type, ...]] = set()
        self._sources: dict[str, str] = {}
        self._compile_errors: dict[str, str] = {}
        self._native_errors: dict[str, int] = {}
        self._hits = self._fallbacks = self._failures = 0
        self._compile_seconds = 0.0
        self._disabled_reason = ""
        self._uses_range = False
        self._node: ast.FunctionDef | None = None
        try:
            if sys.implementation.name != "cpython" or sys.version_info < (3, 12):
                raise ValueError("native extensions need CPython 3.12+")
            if sysconfig.get_config_var("Py_GIL_DISABLED"):
                raise ValueError("the prototype requires a conventional GIL build")
            if sys.platform != "linux" or platform.machine() not in ("x86_64", "AMD64"):
                raise ValueError("native extensions are currently tested on Linux x86-64")
            self._node, self._uses_range = _source(function)
            if self._uses_range and self._range_binding() is not _RANGE:
                raise ValueError("range is shadowed")
        except (OSError, TypeError, ValueError, SyntaxError) as error:
            self._disabled_reason = str(error)
        functools.update_wrapper(self, function, updated=())

    def __get__(self, instance, owner=None):
        # Unsupported methods must retain ordinary CPython argument binding.
        return self if instance is None else MethodType(self, instance)

    def _range_binding(self):
        return self._function.__globals__.get("range", self._function.__builtins__.get("range"))

    @staticmethod
    def _signature_name(signature: tuple[type, ...]) -> str:
        return ",".join(kind.__name__ for kind in signature)

    def adaptive_stats(self) -> dict:
        """Return an independent, JSON-serializable snapshot."""
        return {
            "signatures": {self._signature_name(key): count for key, count in self._profiles.items()},
            "variants": [self._signature_name(key) for key in self._variants],
            "native_hits": self._hits,
            "fallbacks": self._fallbacks,
            "compile_failures": self._failures,
            "compile_seconds": self._compile_seconds,
            "sources": dict(self._sources),
            "compile_errors": dict(self._compile_errors),
            "native_errors": dict(self._native_errors),
            "disabled_reason": self._disabled_reason,
        }

    def _fallback(self, args, kwargs):
        self._fallbacks += 1
        return self._function(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        if self._disabled_reason or self._function.__code__ is not self._code or threading.get_ident() != self._owner or sys.gettrace() is not None or sys.getprofile() is not None or kwargs or len(args) != self._code.co_argcount:
            return self._fallback(args, kwargs)
        if self._uses_range and self._range_binding() is not _RANGE:
            return self._fallback(args, kwargs)
        signature = tuple(type(arg) for arg in args)
        if any(kind is not int and kind is not float for kind in signature):
            return self._fallback(args, kwargs)
        if any((type(arg) is int and not _I64_MIN <= arg <= _I64_MAX) or (type(arg) is float and not math.isfinite(arg)) for arg in args):
            return self._fallback(args, kwargs)
        if signature in self._profiles:
            self._profiles[signature] += 1
        elif len(self._profiles) < self._limit:
            self._profiles[signature] = 1
        if signature in self._variants:
            try:
                result = self._variants[signature](*args)
            except (OverflowError, ZeroDivisionError) as error:
                # There are no user callbacks or mutable values in this subset.
                # Replay before exposing native arithmetic limits/error messages.
                kind = type(error).__name__
                self._native_errors[kind] = self._native_errors.get(kind, 0) + 1
                return self._fallback(args, kwargs)
            self._hits += 1
            return result
        result = self._fallback(args, kwargs)
        if (type(result) is not int and type(result) is not float) or self._function.__code__ is not self._code:
            return result
        if signature not in self._profiles:
            return result
        self._warmups[signature] = self._warmups.get(signature, 0) + 1
        if self._warmups[signature] < self._warmup or signature in self._attempted:
            return result
        self._attempted.add(signature)
        node = copy.deepcopy(self._node)
        assert node is not None
        node.name = "kernel"
        for parameter, kind in zip(node.args.posonlyargs + node.args.args, signature):
            parameter.annotation = ast.Name(id=kind.__name__, ctx=ast.Load())
        node.returns = ast.Name(id=type(result).__name__, ctx=ast.Load())
        node.decorator_list = [ast.Name(id="export", ctx=ast.Load())]
        source = "from ffi import export\n\n" + ast.unparse(ast.fix_missing_locations(node)) + "\n"
        key = self._signature_name(signature)
        self._sources[key] = source
        start = time.perf_counter()
        try:
            # On Linux, dlopen retains the loaded code after its file is removed.
            # Each variant has its own unique module name; no reimport is needed.
            with tempfile.TemporaryDirectory(prefix="pystachy-adaptive-") as directory:
                name = "_pystachy_adaptive_" + uuid.uuid4().hex
                self._variants[signature] = _compile_variant(source, self._compiler, Path(directory), name)
        except Exception as error:
            self._failures += 1
            self._compile_errors[key] = f"{type(error).__name__}: {error}"
        finally:
            self._compile_seconds += time.perf_counter() - start
        return result


def specialize(function=None, *, warmup: int = 3, max_variants: int = 2, compiler: Sequence[str] | None = None):
    """Learn bounded exact int/float signatures and compile pure numeric functions.

    Compilation happens synchronously after ``warmup`` successful Python calls;
    that call returns its original Python result. Later matching calls use the
    extension, on its importing thread. Unsupported kernels remain Python.
    ``compiler`` is an argument vector, normally ``[python, pystachy.py]``.
    """
    if type(warmup) is not int or warmup < 1 or type(max_variants) is not int or max_variants < 1:
        raise ValueError("warmup and max_variants must be positive integers")
    if compiler is not None and (isinstance(compiler, (str, bytes)) or not compiler or any(not isinstance(arg, str) for arg in compiler)):
        raise ValueError("compiler must be a nonempty sequence of strings")

    def decorate(target):
        if not isinstance(target, FunctionType):
            raise TypeError("specialize expects an ordinary Python function")
        return _Adaptive(target, warmup, max_variants, compiler)

    return decorate if function is None else decorate(function)
