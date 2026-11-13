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
by address, class and index. Each can change arbitrarily where the program may write them, a
list's length to at most 2^62 items, which no memory holds.

Facts relate values: equality, signed and unsigned order, a lower and an upper bound by a
constant, a difference bound `a + k ≤ b`, `0 ≤ i < n`, an exact offset, an exact sum of two
values, inequality to a constant, a list's length, a dict lookup's result or live entry, a field's value, and a fact
that marks a point no execution reaches. The certificate is an
untrusted list of facts at each point. Each fact must survive the node before it or follow from
the facts there, and from the facts listed before it, by one of fixed rules, each proved sound:
for example, an unsigned `i < n` of a nonnegative `n` gives `0 ≤ i < n`, and `-1 <u n` cannot
hold for one. A checked addition gives an offset only on the path where its sum fits; a wrapping
one only where the facts show it fits, as for a constant added to an exact offset of a value
that brings it no higher than that value (`n - 3 + 2`). A write to a field of a class keeps the
values of the class's other fields, of any object, and no other field's: a base and a derived
class may view one object differently.

Difference bounds and upper bounds prove `listguard`'s copies of range loops. A test before the
loop, `stop <= len(xs) - c`, gives `stop + c ≤ n` for the length `n`; the loop's own test `i <
stop` and the index `j = i + c` chain to `j + 1 ≤ n`, which with `j ≥ 0` is `0 ≤ j < n`. A 1-based
loop's test, `stop <= len(xs) + 1`, adds to a length, which with at most 2^62 items cannot wrap.
Where the stop is a constant, the loop's test bounds `i` above, the test before it bounds the
length below, and the first must lie under the second.
Sums prove copies whose index adds a base `b` that no iteration changes (`data[bi + d]`). The
tests before the loop give `b ≥ -start - c` and, through `t = stop + b`, a checked sum, `t + c ≤ n`;
the copy's `j = b + i` is a plain sum, which gives the fact `j = b + i` only where `i < stop`,
`t = stop + b` and lower bounds of `i` and `b` show it fits. Adding `b` to both sides of `i < stop`
gives `j < t`, which chains to `j + c < n` as above, and the lower bounds add up to `j + c ≥ 0`.
Certificate inference retains the finite positive lower bounds requested by initial
constants and negative offsets. Thus a loop starting at 1 and advancing by 2 keeps
`i >= 1` at the join of its initial and later iterations. Each proposed weakening
is checked by the existing Lean rule; an invalid start or descending induction
still fails the access proof.

The build checks 46 examples by kernel reduction: 14 shapes the compiler emits and 32
corruptions that must fail: a signed test of a possibly negative index, a list write between a
test and its read or in a range loop's body, a missing or weaker unpacking check, a starred
tail's read at the length or past an offset that may wrap, a lookup's missing-key branch or an
iteration's end, a dict write before an entry's reuse, an entry of one dict used with another, a
reload across a write of another class's field or of the same field of any object, an unguarded
join, facts assumed at entry or around a loop, a guarded range loop's read past the test's
offset, after a list write, or where the test failed, and a base copy without its test of the
base, with an unchecked sum of the stop and the base, with a loop that runs to its stop
inclusive or stores its base, or reached where the length test failed. `Audit.lean` checks the theorem's axioms as
for the payload checker.

## How IR reaches the model

The adapter reads the typed-after snapshot and emits a node for each operation:

- Private slots, and module globals and class variables that the function only loads and stores
  directly, are values; a load copies one and a store assigns it. A global may change wherever
  an operation may write globals. An object field's load and store read and write its cell,
  named by the object's register and the field's class and index; a store of a constant or an
  unknown value writes that field alone too. A field address's operands, like a test's, are SSA
  values, unchanged wherever its result is used.
- Native list, dict and set references loaded repeatedly from a recognized closure cell use
  the same heap model. A cell pointer must come from a constant pointer slot of an `env`-typed
  environment. Writes through the cell or any potentially aliasing address, object writes,
  callbacks and generator suspension invalidate its content. Arbitrary pointers and different
  cells cannot borrow its equality facts. This relies on the closure environment's cell ABI.
- `list.len`, and a word load at the address of a register the IR types as a native list (a
  `List` is `{len, cap, a}`), read a length. `num.cmp` and `int.ucmp` of ints, and `ptr.cmp`,
  become tests of their branch or `check`. `scalar.bin` adds a constant or two values; an `ovf`
  of a constant or of two values whose flag only its block's terminator tests splits its block's
  rest into the path where the sum fits and the path where it overflows.
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
  nonnegative branch must use a live entry. `listguard`'s unchecked item store (`list.store`)
  is a `load`: it has the read's obligation, and the model tracks lengths, not items. A checked
  item assignment (`list.set`) changes no list's length either: it raises `IndexError` or
  stores one item. A phi of -1 and of lookups of one dict, each of which only a jump separates
  from the phi, is that dict's lookup there.
- Every other operation defines its results with unknown values, and so does any other phi. What
  it may change comes from its effects: a runtime operation's `RUNTIME` entry, with a possible
  user-code effect (`U?`) resolved from its descriptor as the compiler does; a direct call's
  summary from the snapshot, strengthened by an independent scan of every visible function
  body and transitive direct callees; anything for an indirect call, an `init` or a generator resumption.
  A list write or user code may change every list's length, except that `list.slice` writes only
  the new list it returns; a dict write every dict's entries; an object write every field.
- Edges are those of `check_lean_boundary.py`: terminator targets, an invoke's unwind edge, each
  `check`'s error block and, from every point of a block a `try` statement covers, its landing
  block. An operation's effects precede the exception edge from it.
- Where a generator suspends (`gen.start`, `gen.yield`), its caller runs: any list, dict, field
  or global may change, though not the generator's own slots, and a `throw()` or `close()`
  raises there.

`check_lean_effects.py` computes the body-write closure independently of the compiler's
effect analysis, including mutually recursive calls and module initializers. It unions those
writes with declared summaries, preserving conservative metadata. An understated summary
cannot hide a visible mutation from an access proof; missing bodies or summaries remain
unknown. Runtime effect contracts, address classification and the Python scan remain trusted.
Negative controls erase summaries above list/dict mutation, callbacks and transitive calls;
Lean must still reject the stale access.

The adapter suggests facts by a forward analysis with the same rules, then lists at each point
only the facts that an access needs, directly or through the facts that justify them. A node
with several predecessors is reached through a jump of its own from each.

## Coverage of compiled code

A sweep on 2026-11-11 at
[`06f65d73`](https://github.com/den-run-ai/pystachy/commit/06f65d731f8c999c5a88490de6930550fa89f930),
with the negated-guard fix, the direct-entry coverage corrections and `listguard`, compiled
every differential test program and deviation of that revision with the hosted compiler: 2,415
programs; 1,180 of them have unchecked accesses, 85,989 in 16,134 functions. Lean accepted every
function but one, proving 85,988 accesses. The earlier sweep at
[`12cca46d`](https://github.com/den-run-ai/pystachy/commit/12cca46dcffd8ee9290d9cf362ba3f4bafb34511),
before those corrections, proved 84,730 of 84,731 accesses in 2,407 programs; selected-corpus
qualification after the corrections is recorded in
[#1241](https://github.com/den-run-ai/pystachy/pull/1241). The exception in both sweeps is
`fib_memo`'s `fib` in [`closures.py`](../../tests/programs/language/closures.py): it loads its
captured dict from the closure's cell for `k in memo` and again for `memo[k]`, and the adapter
does not track cells, so it cannot tell that the second load gives the dict whose entry the
first lookup found. The current adapter recognizes those closure cells and proves the
previously unproved access; a focused replay of `closures.py` proves all eight inventoried
accesses. The whole-program numbers above remain historical until that sweep is rerun.

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
- The runtime contracts the adapter relies on: `RUNTIME`'s effects and the conservative
  descriptor rule for `U?`, the independent body-effect scan, the unpacking checks, the
  lookups' and iteration steps' results, entry writes moving no entry, `list.slice` changing no
  other list, `list.set` changing no length, lists holding at most 2^62 items, and the `List`
  header layout. Declared summaries come from the compiler's own analysis and are
  strengthened by the independent body scan.
- Closure environments containing pointers to mutable cells in their constant pointer slots.
- Fields of one class at different indices being distinct memory, for any objects; fields of
  different classes are treated as possibly the same memory.
- Null checks the `nullcheck` pass removes are not yet normalized: the model's `deref` node
  and its rules are in place for them.
- Source-language or LLVM equivalence, GC, allocation and aliasing beyond the rules above,
  termination or performance.

The CLI runs compiled Lean code, so its result also trusts the Lean compiler, runtime and
JSON/IO front end; the theorem's proof and axiom audit use the kernel. Continue the ordinary
CPython differential, JIT/AOT and GC validation when changing behavior.
