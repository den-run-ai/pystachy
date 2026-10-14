# sortedcontainers 2.4.0: port reference

[Port guide](PORT.md) · [All ports](../README.md)

Upstream hashes identify the inputs used for this adaptation. Validation counts, build times
and benchmark timings below are historical snapshots from the port work; they have not been
rerun for every compiler change. Consult the [language guide](../../docs/language.md) for
current compiler features rather than inferring them from the adaptations.

## Upstream provenance

Source archive: `sortedcontainers-2.4.0.tar.gz`. License: Apache-2.0; see [LICENSE](LICENSE)
and [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES).

Archive SHA-256: `25caa5a06cc30b6b83d11423433f65d1f9d76c4c6a0c90e3379eaa43b9bfdb88`.

| file | upstream SHA-256 | edits |
|---|---|---|
| `__init__.py` | `5ff5f92ee463bdeefb2b0b8942b0d44aed13f39e7d61ca28c106c09e3b8ced31` | 1 (the imports of `SortedSet` and `SortedDict`) |
| `sortedlist.py` | `af003574cf1c7b4f5e6f60cc8cb39f1e88a4842c7f45f9399ee13f352b1faf72` | 97 marked edits in 48 diff hunks |

## Adaptation record

- `SortedList` is specialized to `int` and drops its ABC base, `__new__` key dispatch and key property. Sublist/index-tree algorithms are retained.
- Typed forwarding methods replace aliases; direct comparison methods replace generated operator closures.
- `_concat()`, comprehensions and list operations replace reduce/itertools paths. Iteration, `irange()` and `islice()` materialize their values.
- Ninety-seven marked edits in forty-eight hunks adapt `sortedlist.py`; the package omits imports of SortedDict and SortedSet.

## Validation snapshot

`tests/port_sortedcontainers_api.py` runs the examples of the docstrings, with ints for their
letters, then edge cases: an empty list (every lookup, and the `IndexError` and `ValueError` of
`pop`, `remove`, `sl[0]`, `index` and `del`), duplicates, negative values and both ends of the
64-bit range, `index()` with negative and empty `start`/`stop`, every `inclusive` and `reverse`
form of `irange`, `islice` with negative and out-of-range bounds, indices out of range by one
and at 2**63 - 1 and -(2**63 - 1), copies, `+`, `+=`, `*` (by 0 and by -3), `*=`, the methods
that raise `NotImplementedError`, and the comparisons: `==` and `!=` of copies, ordering by item
and by length, `in`, `count()` and `index()` of lists of sorted lists, also with `None` among
them, `sorted()`, `min()` and `max()` of sorted lists, sorted lists inside tuples and dicts, and
`==` and `remove()` of lists of optional sorted lists; then the methods called with keyword
arguments, by upstream's parameter names, also through the aliases written as defs.
`tests/port_sortedcontainers_index.py` gives about 200 values a load factor of 4 (`_reset(4)`),
so they split into dozens of sublists: it prints the sublists' sizes, `_offset` and the index
tree, and checks `SortedList._check`'s invariants, after positional reads, adds that split
sublists, removes and deletes that merge them, pops at both ends and inside, `update`'s two
paths (value by value, and a rebuild), `irange` and `islice` across many sublists, and 2,100
adds at the default load factor, which split one sublist.

`tests/run.sh` compares what they print with CPython's, JIT and AOT. Run under CPython against
the unmodified upstream package, both print exactly what they print against this port. Both are
small: with the native compiler, the JIT runs take 0.3 s each and the AOT builds 1.6 s and 1.1 s
of CPU time (the executables run in under 0.01 s); under `make verify`'s gc-stress stage (the
compiler collecting every 1,000 allocations, the program at every allocation: 1,853 and 2,660
collections), the JIT run and the AOT build and run take 2.2 s and 1.5 s of CPU time in all
(2.9 s and 2.1 s by the clock, medians of 3 on the VM below at a load average of 10 to 15).

## Benchmark snapshot

The headline workload: a running median and rank over a sliding window of 50,000 values, in a
stream of 400,000 values from a linear congruential generator (400,000 `add`, 350,000 `remove`,
a median `sl[n // 2]` and a `bisect_left` per value, and a `count` and an `irange(v, v + 1000)`
every 1,000 values), then 49,990 `pop(len(sl) // 2)`. Median of 3 runs, with process start-up,
on a 4-core x86-64 VM shared with other jobs:

| | wall | CPU |
|---|---:|---:|
| Pystachy AOT executable, this port | 0.193 s | 0.180 s |
| CPython 3.13.16, unmodified sortedcontainers 2.4.0 | 1.733 s | 1.720 s |

That is 9.0 times faster by wall clock and 9.6 times by CPU time. Runs while the VM was busier
took longer by the clock (0.295 s against 2.566 s) and the same CPU time (0.180 s against
1.740 s). Both print the same checksums. The executable is about 100 KB and links only libc,
libm and libgcc_s. sortedcontainers has no C extension, so CPython runs it in the interpreter;
this does not compare it with C libraries of sorted containers.
