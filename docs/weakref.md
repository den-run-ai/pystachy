# Weak references

Pystachy's experimental `_weakref` supports references to ordinary class
instances, callbacks, equality and hashing. A reference returns its target while
that target is alive, then `None` after the tracing collector clears it.
Collection timing differs from CPython's reference counting.

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

## Standard-library compatibility

`lib/weakref.py` adapts CPython's module and imports, but weak containers,
`WeakMethod`, proxies, reference counts and `finalize` remain unsupported.
Importing the module alone does not establish that a `weakref`, unittest, pytest
or pyperf application works. See the
[library compatibility notes](../lib/compatibility.md#_weakref-prototype).

## Contract and limits

### Construction and lifetime

`ref(obj)` and `ReferenceType(obj)` accept ordinary, non-slotted class instances,
including generic and inherited classes. `ref` is an alias for `ReferenceType`.
The reference type reports `ReferenceType` as its `__name__` and `__qualname__`,
and `weakref` as its `__module__`, as CPython does. `ref[T]` annotations preserve
the referent type; calling the reference returns `T | None`.

The constructor takes the referent and an optional callback, both positionally.
The callback must be a function accepting the reference, or `None`. The compiler
rejects builtin containers, scalars, exceptions and slotted instances as targets.
It also rejects keyword callbacks and callbacks that are not functions. CPython
accepts a non-callable callback at construction and reports its `TypeError` when
it tries to call it after the referent dies.

A strong reference keeps the target alive. Once the collector finds the target
unreachable, it clears every surviving weak handle before reclaiming the
object's storage. Cycles reachable only through weak handles do not retain the
target; the implementation does not keep a strong reference on their behalf.

### Callbacks

A callback receives its reference once, after the referent dies. The collector
queues callbacks; the program runs them when it next creates or calls a weak
reference. This differs from CPython, which normally calls them when the last
counted reference to the referent disappears.

The callback rules are:

- For one referent, callbacks run newest reference first.
- A weak reference that has itself died does not call back.
- A callback can create or call weak references. Any callbacks that become due
  are drained too, but the current callback finishes before the next starts.
- If a callback raises, execution continues with the remaining callbacks and
  the program. The report uses CPython's ignored-exception style, with the
  exception's final line instead of a traceback.

### Equality, hashing and reference identity

| Operation | While the referents are alive | After a referent dies |
|---|---|---|
| `==`, `!=` | Compare the referents using their class's comparison. | If either referent is dead, a reference equals only itself. |
| `hash(r)` | Compute the referent's hash once and cache it. An unhashable referent raises `TypeError: unhashable type`. | Return the cached hash; a first hash after death raises `TypeError: weak object has gone away`. |
| `r is other` | Compare the reference objects themselves. | The same identity comparison applies. |

A reference hashed while its referent lives therefore keeps its hash and remains
usable as a dict key or set member. Comparisons require references to the same
target type; other operands cause a compile-time type error where CPython would
return `False`. Direct calls `r.__eq__(None)` and `r.__ne__(None)` return `False`
and `True`; CPython returns `NotImplemented`, which is not supported here.

Collection timing can change equality results. If `c == Point(1, 2)`, then
`ref(c) == ref(Point(1, 2))` is false in CPython: the temporary second referent has
already died. In Pystachy it stays true until a collection clears that reference.

Each constructor call creates a separate reference. CPython and PyPy may reuse
a reference without a callback; Pystachy does not preserve that cache identity.
Two separately created references to one object are unequal after it dies,
where CPython's reused reference still equals itself. This cache is an
implementation detail discussed in CPython issue #16453.

### Representation and attribute access

`repr(r)` uses `<weakref at 0x...; to 'Item' at 0x...>` for a live target and
`<weakref at 0x...; dead>` after clearing. The target's type name is fully
qualified, except for `__main__`. CPython also appends ` (NAME)` when the
referent's class defines `__name__`; Pystachy omits that suffix.

References expose no instance attributes. Programs cannot read or assign the
wrapper's internal fields, including its handle and cached hash. `hasattr()`
reports those fields, `__dict__` and `__weakref__` as absent. `vars()`, direct
`__dict__` access and attribute names known only at run time are rejected.
Calling `r.__init__(obj[, callback])` validates the arguments but leaves the
reference pointing to its original referent.

### Collection timing

The conservative collector may retain an unreachable object because an old
stack word still looks like its address. Clearing is not tied to `del`, scope
exit or CPython's last counted reference. Repeatedly calling `r()` while waiting
for collection can itself keep the target alive. `PYSTACHY_GC=off` prevents
automatic clearing.

Allocations trigger collections, and the optimizer can remove some allocations.
An unused object or fixed tuple whose fields or items are all `int`, `float` or
`bool` may never be allocated by the `allocelide` pass; see
[optimization reference](typed-ir.md#optimizations). An eliminated allocation
cannot trigger collection, so a reference can clear later than the source's
allocation count suggests. The optimizer never removes an object or tuple that
holds a reference: while the program still reads that container, its contents
stay available.

### Unsupported APIs

Proxies, `getweakrefs`, `getweakrefcount`, `_remove_dead_weakref`, weak mappings,
weak sets, `finalize`, reference subclassing and callback introspection through
`__callback__` are outside this contract. A decorated special name cannot provide
`__callback__` here. Matching CPython's `getweakrefcount()` results would also
require its reference-cache behavior. Missing module APIs remain missing.

## Implementation

### Handles and collection order

The [Python wrapper](../lib/_pystachy_weakref.py) stores an opaque, statically
typed `weakhandle[T]`. Its atomic, unscanned memory holds the target, the next
registry link and an optional callback fire function. The registry is not a GC
root.

After strong marking, `weakrefs_sweep` removes unmarked handles and clears
unmarked targets. This happens before `files_sweep`, `trk_sweep` (the independent
`ffi.track` owner queue) and ordinary reclamation can free or recycle storage.
It preserves tracked-owner cleanup and adds one linear traversal of outstanding
handles per collection.

### Callback queue

The wrapper keeps a `Callable[[], None]` fire function that calls the callback
with the wrapper. Keeping the callback's own type as a field would make the
self-referential `ref[T]` annotation and constructor call produce different
specializations.

When clearing a target, `weakrefs_sweep` queues its fire function only if that
function is marked, meaning the wrapper lives. It then forgets the function.
The queue is a collector root and grows with `realloc`; sweeping runs no Python
code, callback or allocation from the collected heap. If a stale word keeps a
handle marked after its fire function dies, the sweep forgets the function
before that memory slot can be reused.

`pys_weakref_fired` removes each queued function once, oldest first. Because the
registry lists newest handles first, this produces newest-reference-first
callbacks for each referent. A reentrancy guard leaves queue draining to the
current caller when a callback makes or calls another reference, so callbacks
finish in sequence.

### Compiler boundaries

Weak-reference lookup has an `I` effect in typed IR. `Gen.canon` only reuses
runtime expressions with effects at most `R`; function summaries preserve `I`
through the Python wrapper. LLVM sees that `weakref_get` reads the handle's
memory, while allocation can invoke `collect` and write existing handles. An
allocation's fresh return value therefore does not make it a pure operation.

Compiler primitives are available only while compiling the wrapper module.
The opaque handle cannot masquerade as a target class instance, so reads cannot
interpret handle storage as referent fields. A third primitive supplies an
object address for `repr()`. `specs.OPAQUE` prevents other modules from accessing
wrapper fields or changing an existing reference through `__init__`;
`specs.TYPEMODS` makes its classes report the module name `weakref`.

## Verification

### Python and compiler tests

The programs below live in [`tests/programs/library`](../tests/programs/library).
They cover supported behavior in JIT and AOT modes, comparing stable results
with CPython.

| Tests | What they protect |
|---|---|
| `lib_weakref.py` | Live identity, mutation and typed references. |
| `lib_weakref_dead.py`, `lib_weakref_transition.py` | Clearing under allocation pressure after dropping strong owners, valid surviving targets and `None` propagation through typed wrappers. |
| `lib_weakref_eq.py`, `lib_weakref_dead_eq.py` | Type names, `hasattr()`, reinitialization, equality, cached and first hashes, dict/set membership and `repr()`. |
| `lib_weakref_callback.py` | Exactly one callback for each cleared reference and none for live targets. |
| `lib_weakref_callback_order.py`, `lib_weakref_callback_nested.py` | Newest-first order and completion before the next callback, including callbacks that create or call references. |
| `lib_weakref_callback_dead_ref.py`, `lib_weakref_callback_raise.py` | No callback from a dead reference and reporting of callback exceptions. |

Public clearing tests use cohorts of targets rather than requiring one specific
target to clear. The transition test first observes every reference alive,
drops the owners, then requires at least one to clear and any remaining targets
to stay valid. AOT inlining can leave a target in a callee-saved register, so
requiring every target to clear would not be portable. Retaining every target
strongly still fails these tests.

The basic callback test allocates nothing in its callbacks, preventing a new
collection between draining the queue and checking references. Tests whose
callbacks allocate hold strong owners during live reads for the same reason.

[`tools/test_typed_ir.py`](../tools/test_typed_ir.py) separately checks that weak
reads before and after an allocating operation have distinct canonical values.
Error cases cover unsupported target types, invalid callback values, keywords,
arity, private primitives and fields, `vars()`, run-time attribute names and
`__init__` argument validation.

### C runtime probe

Run the focused probe from the repository root:

```sh
make weakrefprobe
```

The [probe](../tools/weakrefprobe.c) uses the real C runtime, both normally and
with collection at every allocation. Non-inlined helpers and stack scrubbing
allow it to require exact clearing of deliberately unrooted targets. It covers
live roots, dead self-cycles, small and large targets, allocation after clearing
and pruning 1,000 abandoned handles.

The same targets also use `ffi.track`: live owners must not enter its queue,
and each dead owner must enter exactly once while its weak references clear.
Callback queue checks require that:

- A live target never queues its fire function; a dead target queues a live fire
  function exactly once.
- The queue keeps the function alive across later collections until it is taken.
- A dead fire function is never queued, even if a stale word keeps its handle
  marked.
- The sweep forgets a dead fire function while the target still lives, so it
  cannot later queue another object that reuses that function's slot.

Removing the queue root, the fire-function mark check or that last forgetting
step makes the probe fail. The probe clears its carrier list before dropping
the list root so a stale conservative address cannot invalidate the test.
It also runs under `make verify` and the CI `contracts` group.

The [CPython weakref reference](https://docs.python.org/3.13/library/weakref.html)
defines the comparison behavior.
