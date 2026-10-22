# `_imp` capability and one-thread lock prototype

This is a deliberately small native prototype for
[#491](https://github.com/den-run-ai/pystachy/issues/491). Pystachy resolves
imports while compiling and executes a selected source module's top-level code
at its first runtime import. This change does not introduce runtime module
discovery, an interpreter, `sys.modules`, or Python extension loading. The
compiler loads `lib/_pystachy_imp.py` for `import _imp`; CPython continues to use
its own C module in differential tests.

Every supported call to `is_builtin(name)` explicitly raises
`NotImplementedError`, including names such as `sys`; it does not report a
usable runtime builtin registry. CPython's `importlib` needs that registry and
module creation/execution operations, which this prototype does not implement.
Adding `_io` alone therefore cannot make upstream `importlib` work.

## Contract

| Surface | Prototype behavior |
|---|---|
| `acquire_lock`, `release_lock`, `lock_held` | Shared recursive lock depth for the single executing thread. Balanced nesting and exception unwinding work. Releasing at depth zero raises CPython's `RuntimeError`. |
| `extension_suffixes()` | A fresh empty `list[str]`: no native Python extension-module loader exists. `ffi.extern` loading C symbols does not qualify. |
| `_frozen_module_names()` | A fresh empty `list[str]`: Pystachy has no frozen Python modules. |
| `is_frozen(name)` | `False` for any string, including CPython's `_frozen_importlib`. |
| `find_frozen(name, *, withdata=False)`, `init_frozen(name)` | `None`, CPython's missing-frozen-module result. They do not initialize a module or decode data. |
| `is_frozen_package(name)`, `get_frozen_object(name)` | `ImportError`, as for a missing frozen name in CPython. |
| `get_frozen_object(name, data)` with bytes supplied | Explicit `NotImplementedError`: there is no Python bytecode interpreter. |
| `is_builtin(name)` | Explicit `NotImplementedError`: compiler namespaces such as `sys`, `typing`, and `os.path` are not a CPython-like runtime registry of modules that `_imp` can create. |
| `create_builtin`, `exec_builtin`, `create_dynamic`, `exec_dynamic` | Explicit `NotImplementedError`; no pretend module construction or successful initialization. |

Names must be `str`, `withdata` must be `bool`, and supplied frozen data must be
`bytes`. Outside these types the compiler rejects the call, rather than running
CPython's argument parser. The lock is bookkeeping for the one-thread runtime;
it does not synchronize OS threads and the compiler loader never acquires it.
The prototype follows a normal CPython build's explicit recursive-lock calls,
not the no-op behavior documented for old builds without thread support.

Remaining `_imp` internals (`source_hash`, `_fix_co_filename`, frozen/interpreter
test overrides and `check_hash_based_pycs`) are absent. Use of an absent name is
a compile-time unsupported-name diagnostic. A `.pyc` policy or hash alone would
not provide the missing bytecode execution machinery. The separate opt-in
CPython embedding proposal [#170](https://github.com/den-run-ai/pystachy/pull/170)
is outside this prototype.

## Prior art and source provenance

This is an original typed implementation, not a copied VM import subsystem.
The historical [builtin-module research](https://github.com/den-run-ai/pystachy/blob/51c90881ba2ed354903412beb576c641a1b19b80/docs/prototypes/builtins-research.md) compares the four
prototypes and the existing issue boundaries.

- CPython **3.13.16**, [`Python/import.c`](https://github.com/python/cpython/blob/v3.13.16/Python/import.c),
  blob `44d0e5420cfe02538a9d6b13b586297b86fca30a`, is the behavioral oracle.
  Its runtime builtin table, frozen code objects and extension loader explain
  why listing compiler pseudo-modules as loadable builtins would be misleading.
- PyPy's **py3.11** implementation,
  [`interp_imp.py`](https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/module/imp/interp_imp.py)
  and [`importing.py`](https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/module/imp/importing.py),
  derives `is_builtin` from its object-space module registry and implements a
  recursive import lock. Its runtime module objects and RPython facilities
  cannot be transplanted as an ordinary Pystachy library module.
- GraalPy's [`ImpModuleBuiltins.java`](https://github.com/oracle/graalpython/blob/7e7182b1036d56f8e89ecc9c7a86cee292180aa6/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/builtins/modules/ImpModuleBuiltins.java)
  uses a context module registry, a JVM `ReentrantLock`, and C-extension loading
  support. Its observed release-without-ownership behavior differs from
  CPython's error; this prototype follows CPython for that case. The useful
  design lesson is to report actual runtime capabilities, not its suffixes or
  registry contents verbatim.

## Evidence and next step

`tests/programs/imports/imp_lock.py` differentially exercises recursive locking around statically
imported `math.sqrt`, alias-shared state, error unwinding, release-underflow,
and missing frozen-module queries against CPython 3.13.16.
`tests/deviations/imp_capabilities.py` contains a small source-file discovery
consumer using the lock and suffix query, verifies returned lists are fresh,
and checks the explicit unsupported-operation messages. Both run in JIT and
AOT, including the suite's GC-stress configuration.

Importing `_imp` and executing those APIs are distinct from importing upstream
`importlib`, `unittest`, `pytest`, or `pyperformance`. No such end-to-end workflow
is claimed to be unblocked. On the prototype rebased onto `92a33b48`, isolated
CPython 3.13.16 overlay probes for `importlib` and `importlib.machinery` both
advance to missing `_io` at `importlib/_bootstrap_external.py:27`; importing
`_imp` itself compiles. This is a next-blocker observation, not a stdlib import
count increase. `_io` is merely the first observed compiler error: beyond it,
`is_builtin()` and the module-loading functions still raise, and `sys.modules`
and Python bytecode execution remain absent.

The overlay was made by `tools/import_sweep.py --overlay ./pystachy.py
CPYTHON_LIB build/imp-overlay`, where `CPYTHON_LIB` is the unmodified `Lib/` of
CPython 3.13.16. It excludes modules already shipped in this checkout's `lib/`.
Each probe contains only `import NAME` and is compiled separately with
`PYSTACHY_PATH=build/imp-overlay python3.13 pystachy.py ir PROBE -o /dev/null`.

Further work should adapt a concrete consumer to
static imports and measure it, rather than expand throwing placeholder APIs or
port CPython's runtime importer wholesale.
