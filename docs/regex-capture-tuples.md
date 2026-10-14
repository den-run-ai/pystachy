# Native regex capture tuples

This experiment adds a previously unsupported type to Pystachy's compiler and
runtime. It is a compatibility prerequisite for the unsupported-types investigation,
not an implementation of adaptive tracing or a demonstrated specialization speedup.
The external generator in withdrawn PR #386 and the parked scalar experiment are
not part of this change.

## The missing type

The existing `re.Match.groups()` implementation returns
`tuple[str | None, ...]`. Its length depends on the pattern's capture count.
Pystachy's ordinary tuples have a fixed type and length, so this call previously
failed compilation with an unsupported return annotation.

With `PYSTACHY_VARIADIC_TUPLES=1`, the unchanged implementation now compiles:

```python
import re

match = re.fullmatch(r"(a)(b)?(c)", "ac")
assert match is not None
groups: tuple[str | None, ...] = match.groups()
print(groups)  # ('a', None, 'c')
```

Regex execution still uses the existing bytecode interpreter in `lib/re/_sre.py`,
compiled by Pystachy. No new VM, generated replacement matcher, source rewriting,
CPython execution fallback or alternative capture helper supplies the generic path.

## Compiler and runtime changes

The compiler gives `tuple[T, ...]` a distinct internal type, `vtuple[T]`.
The native representation holds a length followed by scanned 8-byte item slots.
Existing fixed tuples retain their original representation.

- Annotation handling accepts the homogeneous variadic form behind the opt-in flag.
- `tuple(list)` copies the slots; later list mutation cannot change the tuple.
- Fixed tuples convert to counted tuples, and `list(counted_tuple)` creates a copy.
- Length, truth, iteration and integer indexing use the runtime length. Negative
  indices work, and invalid indices raise `IndexError`.
- Generic runtime descriptors support tuple repr, equality and ordering, including
  unmatched optional captures. Immutable optional-element widening preserves the
  correct element storage.
- `tuple(existing_counted_tuple)` preserves identity. The experiment recognizes
  the tuple type and its supported attributes.

The supported element types are `str`, `int`, `float`, `bool` and their optional
forms. The motivating workload uses strings and unmatched capture values; the
numeric cases validate storage and coercions rather than repeat scalar specialization.

Slicing, unpacking, concatenation, repetition, tuple methods, hashing and use as
dict keys remain outside this prototype. Heterogeneous comparisons and arbitrary
recursive elements are not established. Multi-group `findall()` also requires a
result that can switch between string and tuple rows; this change does not supply it.
The feature is disabled by default.

## Profitability gate

`bench/regex_capture_tuples.py` compares an ordinary capture consumer with a
manually concrete three-item tuple consumer. Their bodies are identical; only the
parameter annotations differ. Consumer-only timings construct regex results before
the timer. The end-to-end control uses `Match.group(1, 2, 3)`, so that comparison
also includes different capture construction and cannot isolate consumer typing.

The longer controls did not establish a reliable concrete advantage. Direct field
normalization was slower with the fixed tuple, and full regex plus normalization
was effectively tied. A lightweight field-signature control showed a small,
inconsistent difference. Raw samples, checksums and environment information are in
`docs/benchmarks/regex-capture-tuples.json`.

Final native CPU-time medians, seven interleaved samples on the shared AMD EPYC
host, LLVM 18.1.3, with CPython 3.13.16 hosting compilation:

| Work | Generic | Manually concrete |
|---|---:|---:|
| Field signature, 6.4 million calls | 0.200015 s | 0.203683 s |
| Direct field normalization, 6.4 million calls | 0.564745 s | 0.613844 s |
| Regex plus normalization, 64,000 records | 0.061824 s | 0.060766 s |

Compilation and startup are excluded. The last comparison's paired median ratio
is 1.005, within observed variation. These controlled input shapes are not a
natural type-distribution census. CPU frequency and competing host work were not
recorded, so the samples support no small speedup claim.

Consequently, this change adds no tuple-shape recorder, profile-selected clone or
online recompilation. The proposed connection to skewed types was to observe tuple
arity, guard that shape and compile a concrete consumer with native generic fallback.
The measured gap does not justify adding that machinery for this workload.

## Reproduce

```sh
PYSTACHY_VARIADIC_TUPLES=1 ./pystachy run tests/errors/lib_re_groups.py
make regex-tuples-check REGEX_TUPLE_COMPILER=./pystachy
python3 tools/bench_regex_groups.py --compiler ./pystachy --samples 7 \
    --repeats 1000 --consumer-repeats 100000 --records 64 \
    --json build/regex-capture-tuples.json
```

The integration suite checks original library source preservation and compares
CPython output with native JIT, AOT and per-allocation GC stress. It exercises
0/1/2/3/4/10 captures, defaults, unmatched groups, list aliases, tuple copies,
optional coercions, bounds errors and rejection with the experiment disabled.
