# Lean unchecked-access prototype

The compiler reads some memory without the runtime check that would otherwise guard it:

| Operation | Emitted by | Its safety rests on |
|---|---|---|
| `list.load` | `listget`'s sequence and range loops, `listfast`'s inline reads, unpacking | a length test, the loop's induction and no list write between them |
| `dict.val`, `dict.key`, `dict.entry_set` and the other entry reads and writes of dicts and sets | `dictfuse`, dict and set iteration, lookups the frontend expands | a lookup or an iteration step that found the entry, and no dict write since |

The IR verifier checks these operations' types, not their indices or entries, and a read past a
list's length inside its capacity or a stale dict entry is invisible to ASan. This optional tool,
[check_lean_access.py](../check_lean_access.py), checks every such operation of a completed
typed-after snapshot with a Lean checker, [PystachyAccess.lean](PystachyAccess.lean): each list
read's index must be within the list's current length and each reused entry must still be live,
on every path.

## Build and run

The access checker builds with the payload-guard checker (see the [README](README.md)) and
shares its pinned toolchain. From the repository root:

```sh
make check-lean-boundary PY=python3.13

python3.13 tools/inspect_compiler.py tools/lean_boundary/examples/unchecked_accesses.py \
  --output /tmp/pystachy-access-example --typed-after-only

python3.13 tools/check_lean_access.py \
  --snapshot /tmp/pystachy-access-example/typed-after.json --all
```

`--function` selects one function by exact name or symbol, `--all` every function with an
unchecked access; `--emit NEW_FILE` writes a candidate without checking it. Exit codes and the
report's fields are those of `check_lean_boundary.py`; a rejected function's `message` names
the first access or fact that a Python mirror of the checker cannot justify. Lean's verdict
remains the result.

## What is proved

`PystachyAccess.accepted_access_safe` states that, if `check` accepts a normalized program and
its certificate, every reachable `load` reads an index within the current length of its list,
every `value` uses a live entry of its dict, and every `deref` reads a non-null pointer, for all
well-formed initial states, all nondeterministic choices and every finite execution. Values are
64-bit integers; lists have lengths and dicts live entries, by address, and objects have fields
by address, class and index. Each can change arbitrarily where the program may write them.

Facts relate values: equality, signed and unsigned order, a lower bound, `0 ≤ i < n`, an exact
offset, inequality to a constant, a list's length, a dict lookup's result or live entry, a
field's value, and a fact that marks a point no execution reaches. The certificate is an
untrusted list of facts at each point. Each fact must survive the node before it or follow from
the facts there, and from the facts listed before it, by one of fixed rules, each proved sound:
for example, an unsigned `i < n` of a nonnegative `n` gives `0 ≤ i < n`, and `-1 <u n` cannot
hold for one. A checked addition gives an offset only on the path where its sum fits; a wrapping
one only where the facts show it fits, as for a constant added to an exact offset of a value
that brings it no higher than that value (`n - 3 + 2`). A write to a field of a class keeps the
values of the class's other fields, of any object, and no other field's: a base and a derived
class may view one object differently.

The build checks 36 examples by kernel reduction: 12 shapes the compiler emits and 24
corruptions that must fail: a signed test of a possibly negative index, a list write between a
test and its read or in a range loop's body, a missing or weaker unpacking check, a starred
tail's read at the length or past an offset that may wrap, a lookup's missing-key branch or an
iteration's end, a dict write before an entry's reuse, an entry of one dict used with another, a
reload across a write of another class's field or of the same field of any object, an unguarded
join and facts assumed at entry or around a loop. `Audit.lean` checks the theorem's axioms as
for the payload checker.

## How IR reaches the model

The adapter reads the typed-after snapshot and emits a node for each operation:

- Private slots, and module globals and class variables that the function only loads and stores
  directly, are values; a load copies one and a store assigns it. A global may change wherever
  an operation may write globals. An object field's load and store read and write its cell,
  named by the object's register and the field's class and index; a store of a constant or an
  unknown value writes that field alone too. A field address's operands, like a test's, are SSA
  values, unchanged wherever its result is used.
- `list.len`, and a word load at the address of a register the IR types as a native list (a
  `List` is `{len, cap, a}`), read a length. `num.cmp` and `int.ucmp` of ints, and `ptr.cmp`,
  become tests of their branch or `check`. `scalar.bin` adds a constant; an `ovf` whose flag
  only its block's terminator tests splits its block's rest into the path where the sum fits and
  the path where it overflows.
- `unpack_check(n, k)` continues only where `n == k`, and `unpack_ex_check(n, k)` only where
  `n >= k` (runtime.c raises `ValueError` otherwise). Lookups and iteration steps (`dict.find`,
  `dict.int_find_any`, `dict.next`, `set.next` and their kin, and a dict comparison's lookups,
  `dict.eq_find` and `dict.eq_pair_find`, which restart where a key's `__eq__` changes the
  table) return -1 or a live entry; `dict.entry` and `dict.big_entry` a live entry or raise, as
  `dict.big_put` returns the entry it finds or adds. A write of an entry's value
  (`dict.entry_set`) moves no entry; deleting one (`dict.entry_del` or `set.slot_del`) is a dict
  write after it. A comparison lookup first reads its source entry's key and hash; the adapter
  checks that entry is live before invalidating facts for a callback and recording the target
  lookup's result. `dict.val_or_zero` reads no entry on its negative-index branch; its
  nonnegative branch must use a live entry. A phi of -1 and of lookups of one dict, each of
  which only a jump separates from the phi, is that dict's lookup there.
- Every other operation defines its results with unknown values, and so does any other phi. What
  it may change comes from its effects: a runtime operation's `RUNTIME` entry, with a possible
  user-code effect (`U?`) resolved from its descriptor as the compiler does; a direct call's
  summary from the snapshot; anything for an indirect call, an `init` or a generator resumption.
  A list write or user code may change every list's length, except that `list.slice` writes only
  the new list it returns; a dict write every dict's entries; an object write every field.
- Edges are those of `check_lean_boundary.py`: terminator targets, an invoke's unwind edge, each
  `check`'s error block and, from every point of a block a `try` statement covers, its landing
  block. An operation's effects precede the exception edge from it.
- Where a generator suspends (`gen.start`, `gen.yield`), its caller runs: any list, dict, field
  or global may change, though not the generator's own slots, and a `throw()` or `close()`
  raises there.

The adapter suggests facts by a forward analysis with the same rules, then lists at each point
only the facts that an access needs, directly or through the facts that justify them. A node
with several predecessors is reached through a jump of its own from each.

## Coverage of compiled code

The historical sweep recorded on 2026-11-11 at
[`12cca46d`](https://github.com/den-run-ai/pystachy/commit/12cca46dcffd8ee9290d9cf362ba3f4bafb34511)
compiled every differential test program and deviation of that revision with the hosted
compiler: 2,407 programs; 1,174 of them have unchecked accesses, 84,731 in 16,062
functions. Lean accepted every function but one, proving 84,730 accesses. These historical
adapter counts predate the merge of released alpha.4 main, the negated-guard fix and the
direct-entry coverage corrections. Selected-corpus qualification after these corrections is
recorded separately in [#1241](https://github.com/den-run-ai/pystachy/pull/1241); the broader
sweep has not been rerun. The exception in the historical sweep is
`fib_memo`'s `fib` in [`closures.py`](../../tests/programs/language/closures.py): it loads its
captured dict from the closure's cell for `k in memo` and again for `memo[k]`, and the adapter
does not track cells, so it cannot tell that the second load gives the dict whose entry the
first lookup found.

The checker's first sweep found a `dictfuse` miscompile: a lookup whose dynamic key may run
user code did not end the lookups before it, so `if k in d2: [d1[k], d2[k]]` reused `d2`'s
entry after `d1[k]`'s `__eq__` could empty `d2`, a segmentation fault where CPython raises
`KeyError` (json_repair's `ObjectComparer.is_same_object` has this shape). It is fixed by
[#1236](https://github.com/den-run-ai/pystachy/pull/1236), merged here, with a regression
test. The other functions that sweeps left unproved were gaps of the adapter or the model, which
the rules above close: a dict comparison's lookups, constant field stores, phis of lookups, a
starred tail's offsets and class variables.

`make check-lean-corpus` runs the same check on each dynamic-`Any` corpus program's snapshot;
CI runs it on every code change.

## Trust and coverage limits

Not proved by this version:

- Fidelity of the snapshot and of the Python normalization to the IR's execution: the
  operation roles, edges, path splitting, slot, global and field naming and the effects above.
- The runtime contracts the adapter relies on: `RUNTIME`'s effects and the compiler's
  descriptor rule for `U?`, the function summaries in the snapshot, the unpacking checks, the
  lookups' and iteration steps' results, entry writes moving no entry, `list.slice` changing no
  other list, and the `List` header layout. Effect summaries are the compiler's own analysis.
- Fields of one class at different indices being distinct memory, for any objects; fields of
  different classes are treated as possibly the same memory.
- Null checks the `nullcheck` pass removes are not yet normalized: the model's `deref` node
  and its rules are in place for them.
- Source-language or LLVM equivalence, GC, allocation and aliasing beyond the rules above,
  termination or performance.

The CLI runs compiled Lean code, so its result also trusts the Lean compiler, runtime and
JSON/IO front end; the theorem's proof and axiom audit use the kernel. Continue the ordinary
CPython differential, JIT/AOT and GC validation when changing behavior.
