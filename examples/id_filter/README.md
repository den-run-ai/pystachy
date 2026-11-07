# Bounded integer-ID filters

`idset.py` is an optional pure-Python example library for dense, reusable masks
of document, vertex or row IDs. It compiles with Pystachy without compiler changes
or a foreign dependency. Copy this module beside an application or add this
example directory to its module path; it is not installed as a standard-library
module.

## Run the consumer

From the repository root after building Pystachy:

```sh
python3 examples/id_filter/search.py
./pystachy run examples/id_filter/search.py
./pystachy build examples/id_filter/search.py -o build/id-filter-search
build/id-filter-search
```

`SearchIndex` assigns IDs to positions in a fixed document batch, indexes tags and
languages, and subtracts blocked documents from each language's eligible mask
once. Repeated tag counts use `intersection_count()` without building a result
mask. Fetching matches materializes the intersection and visits its IDs in batch
order. The sample's English Python results are `Native Python arrays`,
`Compiler internals` and `Python graph tools`; a blocked draft and a French
record are excluded. Duplicate tags do not duplicate results. Unknown tags or
languages return an empty result. Rebuild the index when documents or visibility
change; this example does not implement a mutable search service.

For an application importing the module from another directory:

```sh
PYTHONPATH=examples/id_filter python3 application.py
PYSTACHY_PATH=examples/id_filter ./pystachy build application.py -o build/application
```

## API and ownership

```python
from idset import from_ids

candidates = from_ids(127, [0, 62, 63, 126, 63])
allowed = from_ids(127, [62, 63, 64])
assert candidates.intersection_count(allowed) == 2
assert candidates.intersection(allowed).ids() == [62, 63]
```

| Operation | Contract |
|---|---|
| `IdSet(capacity)` | Empty mask of integer IDs in `[0, capacity)`; negative capacity raises `ValueError` |
| `from_ids(capacity, list_of_ids)` | Build a mask; repeated IDs have no effect |
| `add(id)`, `discard(id)`, `contains(id)` | Checked constant-time access; negative IDs and IDs at or above capacity raise `ValueError` even for membership or an empty mask |
| `count()` | Cardinality, scanning all words |
| `ids()` | New list of IDs, ascending and duplicate-free |
| `intersection_count(other)` | Cardinality of the intersection without a result allocation |
| `intersection(other)`, `union(other)`, `difference(other)` | Independent result mask; operands are unchanged |
| `capacity()`, `storage_words()` | Fixed universe size and number of payload words |

Combining different capacities raises `ValueError`, even when both masks are
empty or have the same word count. Equal capacity checks the numeric range;
callers must use the same meaning for each ID. There is no resizing, implicit
ID remapping, generic object membership, persistence format or thread-safety
contract. The API is typed for `int` inputs. Private fields must not be changed.
All storage belongs to ordinary Python/Pystachy objects: no retained C pointers,
foreign release callbacks or external allocation lifetime is involved.

## When this representation fits

Each word holds **63 bits** so every stored value is a nonnegative signed int64,
including a completely full word. This avoids relying on an overflowing signed
`1 << 63`. Bits past capacity remain zero. Under Pystachy the numeric-list element
payload is `8 * ceil(capacity / 63)` bytes per mask, excluding object and allocation
headers. CPython's boxed integers and list references have different overhead.

Boolean operations and counts visit `ceil(capacity / 63)` words, including empty
words. Exporting IDs additionally visits every present ID. At capacity 65,536,
one mask has 1,041 words and 8,328 bytes of native element payload. A packed
int64 ID list has `8 * cardinality` element bytes, so this bitmap has a smaller
payload only above 1,041 IDs in that universe (about 1.59% density). This is a
payload comparison with a packed list, **not** a measurement of Python set or
whole-process memory. Many rare tags over a huge document universe should use
sparse sets, sorted ID lists or an independently evaluated compressed format.

## Correctness and measurement

The existing differential corpus includes
[`example_id_filter.py`](../../tests/programs/apps/example_id_filter.py) and its
CPython-recorded output. It checks independent set and document-scan oracles,
empty and full words, capacities around 63-bit boundaries, duplicates, signed
int64 rejection extremes, universe mismatches, independent returned storage,
changing sparse masks and the benchmark controls. Run:

```sh
make test-py FILES=tests/programs/apps/example_id_filter.py
PYSTACHY_GC_STRESS_PROGRAM=1 make test-py FILES=tests/programs/apps/example_id_filter.py
make test FILES=tests/programs/apps/example_id_filter.py
```

The first two use the CPython-hosted compiler to execute native JIT and AOT
programs; the last uses the self-hosted compiler. Tests join the existing app
corpus and its CI groups. No timing threshold is a correctness gate.

```sh
python3 examples/id_filter/bench.py --compiler ./pystachy --samples 5 --repeats 200 \
    --output build/id-filter-results.json
```

`bench.py` builds `query_bench.py` once, pins itself and child processes to one
allowed Linux CPU, then rotates and reverses the order of CPython/AOT bitmap,
set membership-count, and materializing set-intersection variants. Each case
has an untimed correctness round before sampling; every sample checks its
checksum and full final ID list against a separate CPython set oracle. Empty,
short, dense and sparse inputs are included. IDs are deterministically shuffled
before sampling ranks at the requested stride, so density comparisons do not
also impose a power-of-two ID pattern on the hash tables. One bounded membership
update per query forces each count to observe changing data. All variants apply the same
update, and all three report the same answer.

The worker measures container construction separately from repeated **update
plus count** operations. Input generation, final sorting and witness printing
are outside these timers. Report medians and raw samples; short/empty timings
can be dominated by dispatch and timer noise. AOT compilation is measured
separately when the harness builds the worker. `--executable PATH` reuses a
prebuilt worker and records its digest instead. Shared-host timing is evidence
for these cases, not a promise about other workloads or a general set replacement.

## Recorded experiment

[Raw measurements](results/2026-11-07-linux-x86_64.json) record seven interleaved
samples of 400 updates/counts each, after the untimed correctness round. The
worker and harness were measured from local commit `a92204b9913171e7949975a5e05c2272d92ece5b`;
the report also records source and executable SHA-256 digests. The run used an
AMD EPYC 9V74, Linux x86-64, LLVM 18.1.3 and CPython 3.13.16, pinned to CPU 0.
Optimization, C flags and GC settings used the compiler defaults, with no
benchmark-specific overrides. Source compilation used the CPython-hosted driver
and an already built runtime cache: 1.335 seconds for a 117,816-byte executable.
That is a warm-cache worker build, not a compiler bootstrap time.

**Native AOT medians, microseconds per update plus count:**

| Capacity | Initial IDs per operand | Bitmap | Set membership count | `len(left & right)` |
|---:|---:|---:|---:|---:|
| 0 | 0 | 0.002 | 0.004 | 0.055 |
| 64 | 32 | 0.010 | 0.167 | 0.326 |
| 65,536 | 32,768 | 2.085 | 632.882 | 696.406 |
| 65,536 | 1,024 | 2.044 | 6.366 | 13.530 |
| 65,536 | 16 | 2.119 | 0.116 | 0.237 |

The bitmap scans 1,041 words for every large-universe count. This gives a clear
advantage in the two denser native cases and a clear cost in the 16-ID case.
The update sequence removes initial left-hand IDs, then adds them again when
it cycles through that list; table cardinalities describe initial construction,
not every individual query. These samples do not establish an exact density
crossover or an end-to-end search speedup. Empty/short results are especially
sensitive to dispatch and timer noise.

**CPython medians, microseconds per update plus count, capacity 65,536:**

| Initial IDs per operand | Bitmap | Set membership count | `len(left & right)` |
|---:|---:|---:|---:|
| 32,768 | 89.439 | 1,244.345 | 822.957 |
| 1,024 | 66.293 | 18.852 | 9.746 |
| 16 | 52.693 | 0.429 | 0.310 |

CPython already favors the set controls at 1,024 IDs, whereas this native build
favors the bitmap there. Representation choice therefore depends on execution
mode as well as density.

**Container construction medians, microseconds for both operands, capacity
65,536:**

| Runtime | Initial IDs per operand | Bitmap | Sets for membership count | Sets for intersection |
|---|---:|---:|---:|---:|
| Native AOT | 32,768 | 118.275 | 1,992.445 | 1,997.763 |
| Native AOT | 1,024 | 11.086 | 59.247 | 57.775 |
| Native AOT | 16 | 6.359 | 5.368 | 5.277 |
| CPython | 32,768 | 13,447.186 | 2,849.532 | 2,936.751 |
| CPython | 1,024 | 392.440 | 72.427 | 70.675 |
| CPython | 16 | 27.440 | 3.676 | 3.956 |

The two set columns run the same construction in separate samples. Differences
between them expose ordinary measurement noise. Input shuffling is excluded
from these costs, and query counts alone do not include construction. Large
native bitmap query samples ranged from about 1.985 to 2.270 microseconds;
the raw report retains all samples rather than hiding shared-host variability.
Use a fixed batch with repeated queries to amortize construction. For sparse
IDs or frequently rebuilt data, keep a sparse representation and measure the
whole application before adopting this layer.
