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
from typing import Callable, Mapping, Sequence
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


def _source(function: FunctionType, helpers: Mapping[str, FunctionType] | None = None) -> tuple[ast.FunctionDef, bool]:
    helpers = {} if helpers is None else helpers
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
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load) and child.id not in local_names and child.id != "range" and child.id not in helpers:
            raise ValueError(f"global name {child.id!r} is outside the prototype")
        if isinstance(child, ast.Assign) and any(not isinstance(target, ast.Name) for target in child.targets):
            raise ValueError("assignment targets must be local names")
        if isinstance(child, ast.AugAssign) and not isinstance(child.target, ast.Name):
            raise ValueError("assignment targets must be local names")
        if isinstance(child, ast.For) and not isinstance(child.target, ast.Name):
            raise ValueError("loop targets must be local names")
        if isinstance(child, ast.Call):
            if not isinstance(child.func, ast.Name) or child.func.id in local_names or child.keywords:
                raise ValueError("calls must directly name range or an explicit, unshadowed helper")
            if child.func.id == "range":
                if id(child) not in range_calls or not 1 <= len(child.args) <= 3:
                    raise ValueError("range(...) is only supported directly in a for loop")
                uses_range = True
            elif child.func.id in helpers:
                helper = helpers[child.func.id]
                if len(child.args) != helper.__code__.co_argcount:
                    raise ValueError("helper calls must supply every positional argument")
            else:
                raise ValueError("calls must directly name range or an explicit helper")
        if isinstance(child, ast.Name) and child.id in {"range", *helpers} and isinstance(child.ctx, ast.Load) and child.id not in local_names and not any(isinstance(call, ast.Call) and call.func is child for call in ast.walk(node)):
            raise ValueError("range and helpers may only be called directly")
    if not _always_returns(node.body):
        raise ValueError("every path must end with an explicit numeric return")
    return node, uses_range


def _binding(function: FunctionType, name: str):
    return function.__globals__.get(name, function.__builtins__.get(name))


class _Region:
    """A source-checked pure call graph and all of its Python binding guards."""

    def __init__(self, entry: FunctionType, helpers: Mapping[str, FunctionType]):
        self.nodes: dict[FunctionType, ast.FunctionDef] = {}
        self.codes: dict[FunctionType, CodeType] = {}
        self.ranges: list[FunctionType] = []
        self.edges: dict[FunctionType, dict[str, FunctionType]] = {}
        visiting: set[FunctionType] = set()

        def visit(function):
            if function in visiting:
                raise ValueError("recursive helper graphs are outside the prototype")
            if function in self.nodes:
                return
            visiting.add(function)
            node, uses_range = _source(function, helpers)
            edges = {}
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id in helpers:
                    name = child.func.id
                    helper = helpers[name]
                    if _binding(function, name) is not helper:
                        raise ValueError(f"helper binding {name!r} does not match the supplied function")
                    edges[name] = helper
                    visit(helper)
            if uses_range:
                if _binding(function, "range") is not _RANGE:
                    raise ValueError("range is shadowed")
                self.ranges.append(function)
            self.nodes[function] = node
            self.codes[function] = function.__code__
            self.edges[function] = edges
            visiting.remove(function)

        visit(entry)
        self.entry = entry
        used_names = {child.id if isinstance(child, ast.Name) else child.arg for node in self.nodes.values() for child in ast.walk(node) if isinstance(child, (ast.Name, ast.arg))}
        self.names: dict[FunctionType, str] = {entry: "kernel"}
        for function in self.nodes:
            if function is entry:
                continue
            number = len(self.names)
            name = f"_adaptive_helper_{number}"
            while name in used_names:
                number += 1
                name = f"_adaptive_helper_{number}"
            self.names[function] = name
            used_names.add(name)

    def valid(self) -> bool:
        return (all(function.__code__ is code for function, code in self.codes.items())
                and all(_binding(function, "range") is _RANGE for function in self.ranges)
                and all(_binding(function, name) is helper for function, edges in self.edges.items() for name, helper in edges.items()))

    def source(self, signature: tuple[type, ...], result_type: type) -> str:
        nodes = []
        for function, original in self.nodes.items():
            node = copy.deepcopy(original)
            node.name = self.names[function]
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id in self.edges[function]:
                    child.func.id = self.names[self.edges[function][child.func.id]]
            if function is self.entry:
                for parameter, kind in zip(node.args.posonlyargs + node.args.args, signature):
                    parameter.annotation = ast.Name(id=kind.__name__, ctx=ast.Load())
                node.returns = ast.Name(id=result_type.__name__, ctx=ast.Load())
                node.decorator_list = [ast.Name(id="export", ctx=ast.Load())]
            nodes.append(ast.unparse(ast.fix_missing_locations(node)))
        return "from ffi import export\n\n" + "\n\n".join(nodes) + "\n"


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
    def __init__(self, function: FunctionType, warmup: int, max_variants: int, max_profiles: int, compiler: Sequence[str] | None, helpers: Mapping[str, FunctionType]):
        self._function = function
        self._code = function.__code__
        self._owner = threading.get_ident()
        self._warmup = warmup
        self._limit = max_variants
        self._profile_limit = max_profiles
        self._compiler = tuple(compiler) if compiler is not None else (sys.executable, str(Path(__file__).resolve().parents[1] / "pystachy.py"))
        self._profiles: dict[tuple[type, ...], int] = {}
        self._warmups: dict[tuple[type, ...], int] = {}
        self._variants: dict[tuple[type, ...], Callable] = {}
        self._attempted: set[tuple[type, ...]] = set()
        self._sources: dict[str, str] = {}
        self._native_bytes: dict[str, int] = {}
        self._compile_errors: dict[str, str] = {}
        self._native_errors: dict[str, int] = {}
        self._hits = self._fallbacks = self._failures = 0
        self._profile_evictions = 0
        self._compile_seconds = 0.0
        self._disabled_reason = ""
        self._region: _Region | None = None
        try:
            if sys.implementation.name != "cpython" or sys.version_info < (3, 12):
                raise ValueError("native extensions need CPython 3.12+")
            if sysconfig.get_config_var("Py_GIL_DISABLED"):
                raise ValueError("the prototype requires a conventional GIL build")
            if sys.platform != "linux" or platform.machine() not in ("x86_64", "AMD64"):
                raise ValueError("native extensions are currently tested on Linux x86-64")
            self._region = _Region(function, helpers)
        except (OSError, TypeError, ValueError, SyntaxError) as error:
            self._disabled_reason = str(error)
        functools.update_wrapper(self, function, updated=())

    def __get__(self, instance, owner=None):
        # Unsupported methods must retain ordinary CPython argument binding.
        return self if instance is None else MethodType(self, instance)

    @staticmethod
    def _signature_name(signature: tuple[type, ...]) -> str:
        return ",".join(kind.__name__ for kind in signature)

    def adaptive_stats(self) -> dict:
        """Return an independent, JSON-serializable snapshot."""
        return {
            "signatures": {self._signature_name(key): count for key, count in self._profiles.items()},
            "variants": [self._signature_name(key) for key in self._variants],
            "attempted": [self._signature_name(key) for key in sorted(self._attempted, key=self._signature_name)],
            "profile_limit": self._profile_limit,
            "profile_evictions": self._profile_evictions,
            "native_hits": self._hits,
            "fallbacks": self._fallbacks,
            "compile_failures": self._failures,
            "compile_seconds": self._compile_seconds,
            "sources": dict(self._sources),
            "source_bytes": {key: len(source.encode("utf-8")) for key, source in self._sources.items()},
            "native_bytes": dict(self._native_bytes),
            "region_functions": len(self._region.nodes) if self._region is not None else 0,
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
        if self._region is None or not self._region.valid():
            return self._fallback(args, kwargs)
        signature = tuple(type(arg) for arg in args)
        if any(kind is not int and kind is not float for kind in signature):
            return self._fallback(args, kwargs)
        if any((type(arg) is int and not _I64_MIN <= arg <= _I64_MAX) or (type(arg) is float and not math.isfinite(arg)) for arg in args):
            return self._fallback(args, kwargs)
        if signature in self._profiles:
            self._profiles[signature] += 1
        else:
            if len(self._profiles) >= self._profile_limit:
                # Counts describe calls since admission, not a historical total.
                # Replacing the least frequent resident lets later hot types warm
                # up even if one-off signatures arrived first.
                victim = min(self._profiles, key=self._profiles.get)
                del self._profiles[victim]
                self._warmups.pop(victim, None)
                self._profile_evictions += 1
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
        if (type(result) is not int and type(result) is not float) or not self._region.valid():
            return result
        if signature not in self._profiles:
            return result
        self._warmups[signature] = self._warmups.get(signature, 0) + 1
        if self._warmups[signature] < self._warmup or signature in self._attempted or len(self._attempted) >= self._limit:
            return result
        self._attempted.add(signature)
        source = self._region.source(signature, type(result))
        key = self._signature_name(signature)
        self._sources[key] = source
        start = time.perf_counter()
        try:
            # On Linux, dlopen retains the loaded code after its file is removed.
            # Each variant has its own unique module name; no reimport is needed.
            with tempfile.TemporaryDirectory(prefix="pystachy-adaptive-") as directory:
                name = "_pystachy_adaptive_" + uuid.uuid4().hex
                self._variants[signature] = _compile_variant(source, self._compiler, Path(directory), name)
                artifact = Path(directory) / f"{name}.abi3.so"
                if artifact.is_file():
                    self._native_bytes[key] = artifact.stat().st_size
        except Exception as error:
            self._failures += 1
            self._compile_errors[key] = f"{type(error).__name__}: {error}"
        finally:
            self._compile_seconds += time.perf_counter() - start
        return result


def specialize(function=None, *, warmup: int = 3, max_variants: int = 2, max_profiles: int | None = None, compiler: Sequence[str] | None = None, helpers: Mapping[str, FunctionType] | None = None):
    """Learn bounded exact int/float signatures and compile pure numeric functions.

    Compilation happens synchronously after ``warmup`` successful Python calls;
    that call returns its original Python result. Later matching calls use the
    extension, on its importing thread. Unsupported kernels remain Python.
    ``compiler`` is an argument vector, normally ``[python, pystachy.py]``.
    ``helpers`` explicitly names ordinary pure functions that may be included in
    one guarded native call graph. Calls must be direct, positional and acyclic.
    Every member's code and global helper/range bindings are checked per entry.
    ``max_profiles`` bounds replaceable signature counters independently of the
    lifetime compilation-attempt budget ``max_variants``. Counts restart when a
    signature is evicted and admitted again. Source/binary bytes are reported in
    ``adaptive_stats``; binary bytes include the extension's runtime and glue.
    """
    if type(warmup) is not int or warmup < 1 or type(max_variants) is not int or max_variants < 1:
        raise ValueError("warmup and max_variants must be positive integers")
    if max_profiles is None:
        max_profiles = max(8, max_variants)
    if type(max_profiles) is not int or max_profiles < 1:
        raise ValueError("max_profiles must be a positive integer")
    if compiler is not None and (isinstance(compiler, (str, bytes)) or not compiler or any(not isinstance(arg, str) for arg in compiler)):
        raise ValueError("compiler must be a nonempty sequence of strings")
    if helpers is None:
        helpers = {}
    if not isinstance(helpers, Mapping) or any(not isinstance(name, str) or not name.isidentifier() or name == "range" or not isinstance(helper, FunctionType) for name, helper in helpers.items()):
        raise ValueError("helpers must map non-range identifiers to ordinary Python functions")
    helpers = dict(helpers)

    def decorate(target):
        if not isinstance(target, FunctionType):
            raise TypeError("specialize expects an ordinary Python function")
        return _Adaptive(target, warmup, max_variants, max_profiles, compiler, helpers)

    return decorate if function is None else decorate(function)
