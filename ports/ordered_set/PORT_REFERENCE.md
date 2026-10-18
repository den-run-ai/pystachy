# ordered-set 4.1.0: port reference

[Port guide](PORT.md) · [All ports](../README.md)

Upstream hashes identify the inputs used for this adaptation. Validation counts, build times
and benchmark timings below are historical snapshots from the port work; they have not been
rerun for every compiler change. Consult the [language guide](../../docs/language.md) for
current compiler features rather than inferring them from the adaptations.

## Upstream provenance

Source archive: `ordered-set-4.1.0.tar.gz`. License: MIT; see [LICENSE](LICENSE)
and [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES).

Archive SHA-256: `694a8e44c87657c59292ede72891eb91d34131f6531463aab3009191c77364a8`.

| file | upstream SHA-256 | edits |
|---|---|---|
| `__init__.py` | `cad6b380ab3204a8bdb85b41b7ddfcc97c50b5d6add55082ebcd6cf6cd0232a8` | 44 marked edits |

## Adaptation record

- The class is specialized to `str`, drops its `MutableSet`/`Sequence` bases and accepts typed lists in place of general iterables.
- Method aliases become forwarding methods. `difference_update()` takes any number of lists,
  including none; its temporary set is annotated so that case has an element type.
  The update methods use upstream's temporary builtin sets; `union()`, `intersection()`
  and `difference()` take one list, and the last two test membership in an ordered set.
  Algorithms and stored indices otherwise follow upstream.
- Fancy indexing, generic comparison branches, itertools-based multi-operand union and slice-object support are omitted.
- Forty-four marked edits remain. `__contains__()` and `__eq__()` keep upstream's `Any` parameters. The test suite deliberately retains upstream’s stale-index and duplicate-list behavior.

## Validation snapshot

`tests/port_ordered_set_api.py` runs the cases of ordered-set's own test suite
(`test/test_ordered_set.py` of the sdist, run under pytest there) and the examples of its
docstrings as a program, with `str` items: order, `!=`, the set algebra as methods (`&` as
`__and__()`), copies and identity, `index()` and its `KeyError`, `get_loc()` and
`get_indexer()`, `discard()` in place of `remove()`, `clear()`, `update()`'s results, `pop()`
down to its `KeyError`, the empty repr, and the operator consistency checks: the `*_update`
methods against the methods that return a new set (equal results, distinct objects) and
`issubset()` and `issuperset()` against a direct test, over upstream's four fixed pairs, 20
pairs of 20 pseudo-random items (a linear congruential generator in place of
`random.Random(0)`) and the pair of `test_bitwise_and_consistency`. It leaves out what the port
leaves out (pickling, slices, fancy indexing, tuple items, `remove()`, the operators, and
comparisons with lists, tuples, deques, sets, dicts and iterators).

`tests/port_ordered_set_edges.py` takes the edge cases that the evaluation of this port met and
that its independent check added: the empty set (each lookup and its error, the set algebra);
quotes, escapes, 2-, 3- and 4-byte UTF-8, NUL, DEL, a zero-width space and the empty string as
items, in the repr and as `KeyError`s; indices out of range by one and at 2**63 - 1,
-(2**63 - 1) and -2**63, for `s[i]` and `pop(i)`; what `add()`, `append()` and `update()`
return; `pop(1)` and what `index()`, `discard()`, `s[i]` and `pop()` do after it (the preserved stale-index bug);
`discard()`'s reindexing; duplicates in the lists the set algebra takes (`issuperset()` of
`["a", "a", "a", "a"]` is `False` for a set of 3, by its length test, and
`symmetric_difference_update()` with a duplicate puts it in `items` twice); `==` and `!=` with
copies, reorderings and `None`, and `in`, `index()` and `count()` of lists of sets; iteration in
the tested consumer forms; and 3,000 tokens deduplicated, with `index()` of each, 143 `discard()`s
and the lookups again. The port's review added more items that `repr()` escapes or keeps (a
no-break space, a soft hyphen, U+2028, an unassigned code point, a combining accent, a byte order
mark, U+10FFFF, a flag of two code points, `%s`), items that differ only after a NUL, items of
10,001 characters, sets changed while a `for` loop iterates them (it steps on through `items` as
CPython's list iterator does, and changing the size of `map` while iterating it raises CPython's
`RuntimeError`), `add()` after `pop(0)` (it gives the new item the stale index of the last
one), the truth of an `OrderedSet | None`, keyword arguments, sets given their own `items`, and a
set as another class's field.

`tests/run.sh` compares what they print with CPython's, JIT and AOT. Run under CPython against
the unmodified upstream package, both print exactly what they print against this port. Both
pass JIT and AOT with `PYSTACHY_IRCHECK=1`, with the native compiler (also with
`PYSTACHY_OPT=-all`) and with the CPython-hosted one; `tools/check_ir.sh` accepts their IR, and
`tests/run.sh` passes as a whole (1,935 passed, 0 failed). They are small: with the native
compiler, the JIT runs take 0.12 s and 0.16 s, the AOT builds 1.0 s and 1.4 s, and the
executables run in 0.003 s. In `make verify`'s gc-stress form (the compiler collecting every
1,000 allocations, the program at every allocation), the JIT run and the AOT build and run of
`port_ordered_set_api` take 1.4 s in all, and those of `port_ordered_set_edges` 1.8 s: medians
of 3, wall clock, on a 4-core VM at load 1 to 2, where CPU time was within 0.02 s of it.

## Benchmark snapshot

The headline workload: 600,000 tokens from a linear congruential generator (`"tok%d"` of 60,000
values) deduplicated into an `OrderedSet` of 59,998, `index()` of each of the 600,000, 200
`discard()`s (each walks the 59,998 entries of `map` to decrement the indices after the one it
removes), then `in` of each token again and `index()` of the 598,031 still in the set. Median of
5 runs, wall clock with process start-up and CPU time, on a 4-core x86-64 VM (load 1):

| | wall clock | CPU |
|---|---:|---:|
| Pystachy AOT executable, this port | 0.309 s | 0.308 s |
| CPython 3.13.16, unmodified ordered-set 4.1.0 | 1.634 s | 1.634 s |
| CPython 3.13.16, this port | 1.261 s | 1.258 s |

All three print the same checksums. The executable is 5.3 times faster than CPython on upstream,
and 4.1 times faster than CPython on the same edited code. Another set of 5, at load 3, took
0.293 s, 1.618 s and 1.281 s of CPU; the first runs, while the VM ran other jobs (load 13 and
14), took 0.297 to 0.307 s, 1.638 to 1.704 s and 1.287 to 1.294 s of CPU.

Part of the difference comes from an edit: upstream's `index()` first tests
`isinstance(key, Iterable)` against typing's ABC, 1.2 million times here, and the port drops
that generic iterable branch; CPython running upstream with only those two lines removed takes
1.26 s of CPU, as it does on the port. ordered-set has no C extension, so CPython runs it as
Python everywhere. The executable is 72 KB and links only libc, libm and libgcc_s. The
evaluation that made the port measured, in wall clock, 0.30 to 0.34 s for the executable, 1.58
to 1.78 s for CPython on upstream and 1.30 s for CPython on the port.
