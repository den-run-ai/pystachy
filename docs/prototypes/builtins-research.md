# Missing builtin prototypes: implementation references and boundaries

Research checkpoint: 2026-10-17. Pystachy's source reviewed here is
`dbac05d7d4ab02ffdc737497cff940b4e95ec278` (through #629). This is architectural
guidance for separate prototypes, not a claim that their APIs have shipped.

## Scope and existing decisions

The current bodies of [#491](https://github.com/den-run-ai/pystachy/issues/491),
[#11](https://github.com/den-run-ai/pystachy/issues/11), and
[#254](https://github.com/den-run-ai/pystachy/issues/254) were reviewed. Their
2026-10-17 refresh cites a different audit checkpoint, `765564a3`: 142/476
isolated native import programs compiled; throwing C-module stubs raised that
to 146/476. First missing-module counts include `_weakref` 101, `_imp` 32,
and `_ast` 31. These are overlapping barriers, not projected gains from adding
those names. The issues leave native unittest/pytest, pyperf and pyperformance
blocked and do not claim a native full CPython regrtest run.

The important existing decisions are preserved:

- #491 requests useful workloads and actual runtime semantics, excludes a
  wholesale port of CPython's import machinery, and keeps CPython embedding
  (#170) a separate opt-in route.
- Weakref-free `abc` is already a delivered adaptation. Genuine `_weakref`
  requires collector support; holding a strong reference does not implement it.
- [The porting guide](../stdlib.md#porting-a-library) requires executed APIs,
  CPython/JIT/AOT comparisons and explicit adaptations/deviations.
- [Module rules](../language/modules.md) prohibit user `_weakref.py`-style
  files from silently replacing CPython builtins. New native shims need the
  same explicit loader treatment as the existing `_pystachy_*` modules.

## Four independent slices

| Module | Smallest useful, honest prototype | PyPy / GraalPy architecture to learn from | Boundary that must remain explicit |
|---|---|---|---|
| `_ast` | Construct and inspect a selected node hierarchy, with accurate `_fields` and `_attributes`; test a real tree consumer. | PyPy generates node definitions from ASDL; GraalPy separates public Python nodes from parser SST nodes with conversion visitors and validation. | Nodes and constants alone do not supply `ast.parse`, `compile(AST)`, source locations or pytest assertion rewriting. Unsupported parse/compile must fail clearly. |
| `_imp` | Runtime capability metadata and a reentrant lock within Pystachy's single-thread contract; optionally a separately tested source-hash algorithm if a consumer needs it. | Both runtimes connect `_imp` to their own module registry, import lock and code loader. Their implementations are not standalone portable Python. | Do not advertise CPython extensions, frozen code objects, bytecode execution or runtime imports which the compiler cannot perform. Metadata must describe Pystachy. |
| `_weakref` | Callback-free weak references to supported native user objects, returning the original object while live and `None` after collection. | PyPy uses GC weak pointers plus a per-referent lifeline; GraalPy uses Java weak references and a reference queue. | Strong references are incorrect. Callbacks, proxies, weak containers, finalizers, equality/hash and introspection require their own acceptance evidence; unsupported operations must not silently succeed. |
| `select` | POSIX integer-descriptor `select.select`, finite/zero/omitted timeouts, readiness and error handling, exercised on a real pipe. | Both maintain the mapping from descriptors back to original inputs; both retry interrupted calls against a monotonic deadline. | Exclude unsupported `fileno()` objects, Windows sockets and poll/epoll/kqueue explicitly. Do not expose nonfunctional backend attributes that make `selectors` select them. |

These are separable PRs. A deliberate restriction is acceptable for a prototype;
silently returning successful fake results is not. Benchmark/import counts should
be reported only after running the corresponding consumer against the exact PR
head, separately from hosted tests of a Python adaptation.

## Semantics that affect implementation

### `_ast`

Use CPython 3.13's ASDL schema as the public contract. PyPy's Python 3.11
schema is useful architecture, not a drop-in 3.13 schema. GraalPy's
`AstModuleBuiltins` initializes metadata and compiler flags separately from
`sst2Obj` and `obj2sst`; the latter also validates the result. Pystachy likewise
needs a boundary between its existing internal parser representation and any
public AST objects. Merely exporting `PyCF_ONLY_AST` must not imply that
`compile(..., flags=PyCF_ONLY_AST)` is supported.

Acceptance should cover node inheritance, field order and values, defaults and
unsupported constructor forms, plus the actual chosen tree traversal. Later
parsing needs UTF-8 source locations, syntax failures and round-trip validation.

### `_imp`

Do not copy the other runtime's capability answers. PyPy determines builtin
status from its registry and whether a module is already initialized. GraalPy
has a TODO for the reinitializable case. A Pystachy registry is a compiler/runtime
contract, not CPython's `sys.builtin_module_names` copied verbatim.

Source hashes differ across these references: PyPy's reviewed Python 3.11
implementation uses SipHash24; GraalPy uses SipHash13 and writes eight bytes
little-endian. Cross-runtime hash equality must be an explicit selected contract,
verified against the chosen CPython version, rather than inferred from the API
name. Nothing about `source_hash` alone provides `.pyc` compatibility.

Use CPython as the behavioral oracle for balanced recursive acquire/release,
unbalanced release and bad argument types. GraalPy's reviewed `release_lock`
returns without error when the current thread does not hold the lock, so its
implementation must not be assumed to match every CPython edge case.

### `_weakref`

Pystachy's collector is conservative, nonmoving and single-threaded. A raw
referent pointer stored in an ordinary scanned object would retain the object.
A weak cell needs an unscanned representation or a pointer encoding, and its
registry must not accidentally root every weakref wrapper. After marking, clear
dead targets and discard dead weakref records **before** the normal sweep clears
mark bits, reuses slots or frees large blocks. Pointer reuse must never resurrect
an old weak reference.

Delayed collection is expected under a tracing/conservative collector. Test
eventual death after allocation pressure or a controlled collection, with the
creating frame gone; do not require CPython's immediate reference-counting
behavior. Also test a live referent across collection and repeated allocation
at reused addresses. A runtime harness can establish these safety properties
before Python-level type support is complete.

PyPy caches a reference's hash while its referent lives; requesting its first
hash after death raises `TypeError`. Equality compares live referents and falls
back to weakref identity when either referent is dead. Its callbacks run from a
finalizer path in reverse registration order. These are additional features,
not consequences of storing a weak pointer. GraalPy's reviewed module still has
`getweakrefs` returning `None` and `_remove_dead_weakref` marked TODO; they are
not implementation templates. CPython's `_remove_dead_weakref` conditionally
removes an entry only when it contains a dead weakref.

### `select`

Validate descriptor bounds before `FD_SET`, and retain order and duplicates in
the returned lists. A future `fileno()` implementation must return the original
objects, not substitute integer descriptors. Test negative and oversized
descriptors, closed descriptors, empty lists, readable/writable readiness,
zero timeout, negative/nonfinite timeout and finite timeout expiration.

Both Python 3 PyPy and GraalPy retry `EINTR`, dispatch pending signals/actions
and recompute the remaining finite timeout from monotonic time. Repeating the
original timeout can oversleep indefinitely. POSIX may mutate fd sets, so each
retry must rebuild the original interests. GraalPy has a Java-emulated fallback
which returns all inputs for an unselectable channel; do not copy that behavior
into a native POSIX backend. `select.error` is the Python 3 alias of `OSError`.

## Reproducible primary sources

No external implementation code was copied for this research document. If a
prototype later copies code, preserve the source's notices and record the exact
source revision in that PR. PyPy's implementation is MIT licensed; GraalPy's
reviewed Java files carry UPL 1.0 notices; CPython uses the PSF license.

Pinned sources inspected:

- **CPython 3.13.16**, `cbc944f4bc59639a444dd971c737788ba2283a91`:
  [AST schema](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Parser/Python.asdl),
  [import internals](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Python/import.c),
  [weakref module](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Modules/_weakref.c).
  Contracts: [ast](https://docs.python.org/3.13/library/ast.html),
  [weakref](https://docs.python.org/3.13/library/weakref.html),
  [select](https://docs.python.org/3.13/library/select.html),
  [importlib](https://docs.python.org/3.13/library/importlib.html).
- **PyPy Python 3.11 branch**, `3ce8ee955977343ff96902fdedbc5dad535d0f95`:
  [AST module](https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/module/_ast/moduledef.py),
  [ASDL generator](https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/interpreter/astcompiler/tools/asdl_py.py),
  [import module](https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/module/imp/interp_imp.py),
  [weakref](https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/module/_weakref/interp__weakref.py),
  [select](https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/module/select/interp_select.py).
  The default `main` branch was not used as the Python 3 semantic reference.
- **GraalPy**, `7e7182b1036d56f8e89ecc9c7a86cee292180aa6`:
  [AST module](https://github.com/oracle/graalpython/blob/7e7182b1036d56f8e89ecc9c7a86cee292180aa6/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/builtins/modules/ast/AstModuleBuiltins.java),
  [import module](https://github.com/oracle/graalpython/blob/7e7182b1036d56f8e89ecc9c7a86cee292180aa6/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/builtins/modules/ImpModuleBuiltins.java),
  [weakref module](https://github.com/oracle/graalpython/blob/7e7182b1036d56f8e89ecc9c7a86cee292180aa6/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/builtins/modules/WeakRefModuleBuiltins.java),
  [weak cell](https://github.com/oracle/graalpython/blob/7e7182b1036d56f8e89ecc9c7a86cee292180aa6/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/builtins/objects/referencetype/PReferenceType.java),
  [select](https://github.com/oracle/graalpython/blob/7e7182b1036d56f8e89ecc9c7a86cee292180aa6/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/builtins/modules/SelectModuleBuiltins.java).
