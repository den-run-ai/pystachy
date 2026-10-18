# Experimental `_weakref` prototype

This is a collector-backed prototype for the missing builtin tracked in
[#491](https://github.com/den-run-ai/pystachy/issues/491). It is not a complete
`_weakref` implementation. No tested standard-library weakref consumer is
unblocked yet; unmodified `weakref`, `unittest`, `pytest` and `pyperf` remain
unsupported. It does not retain targets strongly to imitate a weak reference.

```python
from _weakref import ref, ReferenceType

class Item:
    def __init__(self, value: int):
        self.value = value

def borrow(item: Item) -> ReferenceType[Item]:
    return ref(item)

item = Item(7)
r = borrow(item)
assert r() is item
```

## Standard-library compatibility is still blocked

With CPython 3.13.16 sources in the import overlay, this prototype rebased on
`92a33b48` produces these results:

| Probe | Result |
|---|---|
| Direct `_weakref.ref(obj)` for the supported class subset | Works in the focused JIT/AOT tests below |
| `import weakref` | Rejected: cannot import `getweakrefcount` from `_weakref` |
| The same, with throwaway definitions of the missing `_weakref` names | Rejected next at `ProxyTypes = (ProxyType, CallableProxyType)`: classes are not values ([#7](https://github.com/den-run-ai/pystachy/issues/7)) |
| `from _weakrefset import WeakSet; WeakSet()` | Rejected: cannot infer the type of `WeakSet.__sub__` |

Importing a module is not evidence that its APIs work. Even after the `WeakSet`
inference error is addressed, its callback-bearing references need semantics
this prototype does not implement. Missing callbacks, proxies and registry
helpers must be implemented and tested before claiming a standard-library
weakref user is supported. Equality and hashing are implemented (below).

## Contract and limits

* `ref(obj)` and `ReferenceType(obj)` accept ordinary, non-slotted class
  instances, including generic and inherited classes. As in CPython, `ref` is
  `ReferenceType`: `type(r).__name__` and `__qualname__` are `ReferenceType`, and
  `__module__` is `weakref`. `ref[T]` annotations preserve the referent type;
  calling the reference yields `T | None`.
* A live strong reference keeps the referent available. Once the collector
  finds it unreachable, every surviving weak handle to it yields `None`, before
  the old object's storage is reclaimed. Cycles reachable only through weak
  handles do not keep a target alive.
* The constructor takes exactly one argument. A second argument, including an
  explicit `None`, is rejected. Callbacks are not implemented. Builtin container,
  scalar, exception and slotted instances are rejected by the compiler.
* `==` and `!=` compare the referents while both are alive, with their class's
  comparison; once either is dead, a reference equals only itself. `hash()` is
  the referent's, computed once and kept, so a reference hashed while its
  referent lived keeps its hash and stays a usable dict key or set member. A
  first `hash()` after the referent died raises CPython's `TypeError: weak object
  has gone away`, and an unhashable referent's raises `unhashable type`.
  References compare only with references to the same type; another operand
  is a compile-time type error where CPython's comparison returns `False`.
* `repr()` is CPython's: `<weakref at 0x...; to 'Item' at 0x...>` with the referent's
  type by its fully qualified name (without `__main__`), or `<weakref at 0x...; dead>`.
* As in CPython, a reference has no attributes of its own. The wrapper's fields
  (the handle and the kept hash) belong to `_weakref`: a program cannot read or
  assign them, `hasattr()` reports them, `__dict__` and `__weakref__` absent, and
  `vars()`, `__dict__` and attribute names known only at run time are rejected.
  `r.__init__(obj)` and `r.__init__(obj, callback)` check their arguments as
  CPython's do and leave the reference to its first referent.
* Each call makes a separate reference. CPython and PyPy may reuse an existing
  no-callback reference; this prototype does not preserve that reference-cache
  identity. `is` still compares the actual reference objects.
* Proxies, `getweakrefs`, `getweakrefcount`, `_remove_dead_weakref`, weak mappings,
  weak sets, `finalize`, callback introspection (`__callback__`) and reference
  subclassing are outside the prototype contract. `getweakrefcount()` would also
  need CPython's reuse of one reference per referent to give its counts. Missing
  module APIs remain missing; no success-shaped placeholder is provided.

Pystachy's conservative tracing collector may retain an otherwise unreachable
object because an old stack word still looks like its address. Reclamation is
not tied to `del`, scope exit or the loss of CPython's last counted reference.
Repeatedly calling `r()` while waiting for collection can itself keep the target
alive. `PYSTACHY_GC=off` naturally prevents automatic clearing.

## Implementation

The Python wrapper stores one opaque, statically typed `weakhandle[T]`. The
handle is allocated in atomic memory and contains the target and the next
registry link. Neither word is scanned. The registry is deliberately absent
from GC roots. After strong marking, `weakrefs_sweep` removes unmarked handles
and clears unmarked targets, before ordinary sweep can free or recycle either.
Weak-reference sweeping runs no callback, allocation or Python code. It runs
before `files_sweep`, `trk_sweep` (the independent `ffi.track` owner queue) and
ordinary reclamation, preserving the existing tracked-owner cleanup.
Collection adds one linear traversal of outstanding handles.

Lookup has an `I` effect in typed IR. `Gen.canon` only reuses runtime expressions
whose effects are at most `R`, and function summaries preserve `I` through the
Python wrapper. LLVM can see that `weakref_get` reads its argument's memory, but
allocation can call `collect`, which writes existing weak handles; allocation's
fresh return value does not make it a pure operation. Review found no stale-read
optimizer bug. A direct canonicalization regression and live-read, last-owner
removal, allocation-only collection, dead-read tests protect these boundaries.
The public tests use cohorts. The transition test first observes every reference
live, then at least one must clear after owners are dropped; any remaining
target must stay valid.
Requiring one particular target to clear is not portable even when its helper
returns: AOT can inline that helper and leave the target in a callee-saved
register throughout later allocation. The Unicode length fast path exposed
exactly this valid conservative retention, not stale-read optimization.
The C probe separately uses non-inlined helpers and stack scrubbing to assert
exact clearing of every deliberately unrooted target.

The compiler primitives are available only while compiling this library
module. An opaque handle does not masquerade as a target class instance; reads
cannot accidentally interpret the handle's storage as the referent's fields.
A third primitive gives an object's address for `repr()`. `specs.OPAQUE` names
`_weakref` as a module whose objects have no attributes in CPython: the compiler
rejects other modules' access to its classes' fields and their `__init__` calls
on existing objects leave them unchanged; `specs.TYPEMODS` gives its classes the
module CPython's types report, `weakref`.

## Reference implementations

* [Python 3.13 weakref contract](https://docs.python.org/3.13/library/weakref.html)
  is the semantic oracle. Unlike reference counting, it permits a target to be
  returned until the object is actually destroyed.
* [PyPy `_weakref`, Python 3.11 branch, revision 3ce8ee9](https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/module/_weakref/interp__weakref.py)
  separates weak pointers/lifelines from strong ownership and implements cached
  hashes and live/dead equality. Those latter contracts are explicitly rejected
  here until implemented. [PyPy's documented GC differences](https://doc.pypy.org/en/latest/cpython_differences.html)
  also explain why immediate refcount timing is not a portable test.
* [GraalPy revision 7e7182b](https://github.com/oracle/graalpython/tree/7e7182b1036d56f8e89ecc9c7a86cee292180aa6/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/builtins/objects/referencetype)
  uses Java weak references and reference queues. This supports keeping target
  clearing tied to collector state, while its asynchronous callback machinery
  is beyond this single-threaded prototype. Incomplete helper stubs are not an
  implementation model for this port.

## Verification

`tests/lib_weakref.py` compares live identity, mutation and typed references
with CPython in JIT and AOT. `tests/lib_weakref_dead.py` creates a cohort of
targets in a returned helper and applies allocation pressure without
dereferencing them, then checks that `None` propagates through typed wrappers.
`tests/lib_weakref_transition.py` first observes every reference live, drops
its strong owners, and checks that allocation pressure clears at least one
reference while any remaining referents stay valid. These cohort assertions
allow a few stale conservative roots; retaining every target strongly still
fails them. `tools/test_typed_ir.py` independently checks that
weak reads on either side of an allocating operation have distinct canonical
values. `tests/lib_weakref_eq.py` compares names, `hasattr()`, reinitialization,
equality, hashing, dict and set membership and the `repr()` format with CPython
while every referent is owned; `tests/lib_weakref_dead_eq.py` checks a dead
reference's identity equality, kept hash and failing first hash on cohorts, as
the transition test does. Error cases cover unsupported target kinds, callbacks,
private primitive access, the module's fields (read, assigned, `vars()`, run-time
names) and `__init__` argument checks.

`make weakrefprobe` includes the real C runtime and runs normally and with a
collection at every allocation. It checks live roots, dead self-cycles, small
and large targets, repeated allocations after clearing, and pruning 1,000
abandoned handles. The same small and large targets are also registered through
`ffi.track`: live owners must not be queued, and each dead owner must be queued
exactly once while its weak references are cleared. It clears its carrier list
before dropping the list root,
so a stale conservative address of that carrier cannot invalidate the test.
The same probe belongs to `make verify` and the CI `contracts` group.

Promotion requires full-suite validation and review of the GC change. Callback
ordering/resurrection, no-callback reference caching, standard-library helper
coverage and supported type coverage remain separate work; this prototype does
not close #491.
