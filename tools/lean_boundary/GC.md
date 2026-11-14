# Collector scanning of container arrays

The collector (runtime.c) is conservative and scans every object except its atomic memory. A list
of ints, floats or bools keeps its items in an atomic array, a dict of such values keeps its values
in one, and a dict or set of int (or bool) keys keeps its keys in one. A pointer stored in an atomic
array is invisible to the collector, which may free the object it points to while the program
still uses it. Differential tests rarely show this: it needs a collection at the wrong moment.
[#603](https://github.com/den-run-ai/pystachy/pull/603) introduced these arrays and chose the
allocator once inference resolved an empty container's type: the property depends on that choice
agreeing with every later use.

[`check_lean_gc.py`](../check_lean_gc.py) proves with Lean, in the finite-tag model, that every use
whose type lets an array hold pointers (a list of strs, a dict of objects, a set of tuples) uses a
value whose array is scanned (or null, which has none), and that words that may be pointers are
written only into scanned arrays.

## Model

Each list or set value has one location and each dict two (its value array, and its key array as
`#keys`); a location's tag is its array's kind, `atomic` or `scanned`. What made the value gives
its tags:

| Producer | Tags |
|---|---|
| `list.new_atomic`, `list.from_const`, `range.list`, `bytes.list`, `m.ufloats` | atomic |
| `list.new`, `dict.new` and `set.new` with a type hole | as lowering allocates for the hole's resolved type (the exported `holes`): atomic items or values for a numeric type, atomic keys for int or bool keys, and an unresolved hole's key kind 0 |
| other `list.new`; `dict.new`, `dict.new_atomic`, `set.new`, `dict.fromkeys` | scanned items or values (atomic values for `dict.new_atomic`); keys by the key kind operand: 0 atomic, 1 or 3 scanned, a hash descriptor atomic where its text (the exported `key_descriptors`) begins with `i` or `b` (`keymem`) |
| a runtime copy (slices, `copy`, `+`, `*`, dict copies, set algebra) | one of its operands' (a list keeps its kind through copies: `atomic_items`) |
| `dict.keys`, `dict.values`, `set.list` | a copy of the source array's location (`col`, `pys_set_list`) |
| `dict.fromkeys_dict` | scanned values, its source's key kind |
| another runtime list | scanned (`pys_list_new`) |
| a phi, a select, a private slot (one only direct loads and stores reach) | its operands' or stored values' (copies); a slot starts null, as lowering zero-initializes it |
| `empty.kind` | a dict's keys, or a set: its old tag or the stored kind's (its next tables have that kind, a table it holds keeps its own; a set's first eight slots are scanned) |
| a parameter, a call's result, an unpacked word | what its declared type allows: either for an array of numbers, scanned for one that may hold pointers; a callee's declared return type, not the use's view |
| a load of a memory word | what the program's stores of that word are checked to hold (below) |

A use's obligation comes from its operand's type, and also from a callee's declared parameter
type at a call, the function's declared return type at a return and the memory word's type at a
store, so a view that disagrees with what it is passed to cannot hide an atomic array. A value's
type may be `S` (a runtime copy's receiver type), an optional or a bound builtin method
(`fn[d:append:list[str]]` is its list): the adapter takes its family from its definition and uses.

Writes are checked whatever any view of their receiver says, so a dict or set that only runtime
functions hold is checked too. An item write (`list.append`, `list.set`, `list.insert`, the
identity forms, `dict.set`, `dict.setdefault`, `dict.entry_set`, `set.add`, and `list.store`,
compiled `l[i] = x`) whose item may be a pointer needs its array scanned. The item's type is its
`*T` operand's, else what made the word: a `slot.pack`'s operand, a `tuple.load`'s item type, the
part of a container's static types that a read of it returns (`dict.pop`, `list.get`, ...), a
phi's or select's operands' or the value's own type; a constant without a global is a number or
null, and an unknown type may be a pointer. A write of another container's words (`list.extend`, `list.set_slice`, `dict.update`,
`dict.update_pairs`, the `set.update`, `set.ixor`, `set.assign` and `set.union_more` forms), and a
result that takes another operand's words (`set.or`, `set.xor`, `set.and_list`, the `set.xor`
list and dict forms, `dict.fromkeys`), needs its array scanned where the source's static types may
hold pointers, or the source's array atomic: an atomic array holds no pointer, since every write
of one into it is rejected. Both are offered; the adapter keeps the one its inferred facts prove,
and Lean checks it. A fresh container that no other operation uses is empty and writes nothing,
and a column's, `dict.items` list's or vtuple's list's static type is its source's part.

A memory word, a module global or class variable by its symbol or a field by its word (as union
memory keys it), is typed once for the program (`memory_types`): its concrete views' arrays, the
strictest where they differ, so a store through a view the compiler left open (`*list[?]`) is
checked against what another view's load assumes (`*list[str]`). The corpus has 91 such globals. A
global every view of which is open holds what its stores hold: the adapter infers that from the
facts of the stored values (with null, since a global starts as null), Lean checks every store
against it, and its loads assume it. A word whose address another operation uses keeps each
access's own view. A list's items or a dict's values that a declared result type leaves open (a
template's empty result, which its caller types) are scanned: a function returning one is
checked for it, and a direct call's result assumes it (`pys_list_new` and `pys_dict_new` make
them).

A generator's suspension (`gen.yield`) is a use of what it yields as its declared yield type
(`gen[T]`), which its consumer's `slot.unpack` assumes: the value a `slot.pack` in the generator
packed, or a constant (a number, or null). Another yielded word is unsupported where `T`'s arrays
may hold pointers. Its first resumption and its end (`gen.start`, `gen.ret`) are edges.

The assumptions at parameters, results, loads and words hold by induction over a run where every
function's obligations are proved: a program's proof needs every function accepted.

## Trust and limits

The runtime's array kinds (allocators, copies, columns and writes keeping their arrays' kinds;
`empty.kind` setting the kind of a dict's or set's next tables), lowering's zero-initialized
slots, the exported type holes and key descriptors, the IR's declared, operand and item types, Callable typing at indirect calls, a
dynamic box's descriptor matching its list's static type (which the payload checker's reads test),
the views of a memory word whose address escapes (none of the corpus's container globals) and the
Python adapter (its static types, item types, inferred global invariants and choice of obligation)
are trusted. The check does not cover pointers stored in other atomic memory (strings,
`Buf` data, hash and index arrays), the collector's roots (stack, registers and registered globals),
`allocelide`'s deletion of reference-free objects, lifetime, or type puns that compiled library
code makes on purpose (`_pystachy_copy`'s memo keeps objects as `str` words and casts them back).
Objects and fixed tuples, `pys_new`'s included, are scanned memory. The boundary validator checks
the IR's form here up to 4,096 blocks and 16,384 instructions, reading a type name past 256
characters by its digest; a function whose graph passes the checker's 16,384 nodes, or with an
operation of more than 256 operands, is unsupported.

The tag model has no emptiness: a template's empty dict or set, typed by its caller's `empty.kind`,
keeps the old tags its open result type leaves unknown, so its keys are rejected where a use
needs them scanned (the runtime keeps them safe: a fresh dict has no table yet, a fresh set's
first table is scanned). A function that returns a call cycle's result as an open type is
checked against what its callee declares, whose numbers' arrays may be atomic.

[`examples/gc_arrays.py`](examples/gc_arrays.py) makes lists, dicts and sets of numbers, strs,
objects and tuples, copies, columns and comprehensions of them, writes items into them, keeps them
in globals and returns a template's empty list; [`test_lean_gc.py`](../test_lean_gc.py) corrupts
its IR as a compiler bug could: a type hole resolved to a list of ints for a list of strs, the
atomic allocator for pointer items, an int key kind for str keys, a set's hole resolved to ints
for tuples, a function returning an atomic list as a list of strs, an atomic list stored where
memory holds a list of strs and one passed for a parameter that is a list of strs; a dict and a
set only runtime functions hold, made atomic where strs are written into them; an int key kind for
a set or for `dict.fromkeys` keys filled with a list's strs; a str stored by `list.store` into a
list of ints; an atomic list stored in a global through an open view; an atomic list in a global
that every view leaves open, appended strs; an atomic open template result; a dict of str keys
re-kinded to int keys by `empty.kind`; and a generator of lists of ints declared to yield lists of
strs. Lean must reject each; disabling each rule makes a control fail.

## Run and coverage

`check_lean_guard_corpus.py` runs the check on each program it inspects (its `gc_*` counts), and
the CI `contracts` group's bounded selection includes `gc_arrays.py`:

```sh
python3.13 tools/inspect_compiler.py tools/lean_boundary/examples/gc_arrays.py \
  --output /tmp/gc-arrays --typed-after-only --guard-evidence
python3.13 tools/check_lean_gc.py --snapshot /tmp/gc-arrays/typed-after.json
```

A sweep on 2026-11-12 of all 2,418 differential programs and deviations (snapshots of the compiler
at `e7ec9bb8`) proved 188,950 of 189,325 obligations in 25,998 functions: 2,377 programs are
proved, 32 rejected and 9 unsupported. 12 are rejected only for the copy memo's pun, 19 for a
template's empty result that its caller types, directly or through a call cycle, and one,
`dict_union_object_keys.py`, for a generic function whose keys stay a type parameter. The
unsupported functions are `html.entities`' initializer and `class_ids_wide.py`'s module code, whose
graphs pass 16,384 nodes, and the `sqids` constructor, which makes a 358-item tuple. The generators
(504 across the corpus), the regex engine's `sre_match` and the constant tables that an earlier
sweep left unsupported raised no rejection. Designing the check found the bug `e7ec9bb8` fixes:
`list(())` allocated an atomic array that its callers typed as a list of strs. The check rejected
`generic_annotations.py` and `iterate_tuples.py` before the fix, and its regressions crash without
it.
