# Bounded regex value specialization

This is an offline experiment following [#384](https://github.com/den-run-ai/pystachy/pull/384).
That receiver-feedback experiment found no useful HTML speedup: ordinary compilation
already supplied the same concrete parser methods. The regex engine's `Pattern`,
`State`, `Ctx`, `list[int]` bytecode and `str` subject types are also already known.
The opportunity here is to specialize **pattern values**, eliminating interpreter
dispatch and making the result's capture count a compile-time constant.

## The unsupported result type

The existing port rejects `findall()` with two or more captures. Its result would
contain tuples whose length comes from a runtime pattern, whereas Pystachy's
tuples have statically fixed lengths. `Match.groups()` has the same problem with
its `tuple[str | None, ...]` annotation. The current port instead exposes fixed
`Match.group(1, 2, ...)` calls through existing variadic templates.

For the date-extraction pattern `(\d{4})-(\d{2})-(\d{2})`, a residual helper can
declare `list[tuple[str, str, str]]`. All of its fallback paths must return that
same type. A pattern with a different capture count therefore cannot be accepted
silently. This is an explicit typed helper, not automatic support for arbitrary
`re.findall()` or variable-length tuple types.

## Scope

The generator reads the existing port's parser and emits ordinary Python source
in Pystachy's supported subset. This first experiment admits bounded fixed-width
patterns with two to five captures, literals, simple character classes,
categories and exact repeats. It rejects branches, lookarounds, backreferences,
variable or lazy repeats and unsupported flags. Generation is explicitly requested;
there is no runtime profiling, tracing, online compilation or cache evolution.
Source length and expansion work are capped at 4,096; residual width is at most
128 characters and exact repeats at most 32. Zero-width repeat bodies are rejected.
Single-character alternatives normalized by the parser to classes are eligible.

A generated matcher guards the pattern value, effective flags and capture count.
The port exposes mutable pattern bytecode, so it also checks that bytecode rather
than trusting a cached identity. Unicode and different same-arity patterns keep
the existing matcher semantics through fallback. The residual and the VM control
share the port's subject decoder and byte-offset model. Engine or runtime files
are unchanged.

The explicit helper contract accepts plain `re.compile()` results with unchanged
matching methods. Port `Pattern` subclasses and monkeypatched methods are excluded:
overridden `_state()` could change matching even with identical bytecode. Unlike
CPython's non-subclassable Pattern, the port permits subclasses, and the current
subset has no public exact-type identity expression. `compatible()` is a metadata
and bytecode eligibility check within this contract, not an exact-class guard.
Automatic call-site integration must add an exact-class guard before admitting
arbitrary Pattern receivers.

## Experimental controls

Compare a fixed-arity VM loop with the residual matcher before integrating any
new feedback machinery. The VM control extracts captures directly from match
state; it does not create an eager list of `Match` objects. Both variants return
the same tuple list, use the same input subjects and include output allocations.
The portable `finditer()` adapter is a separate compatibility fallback, not the
performance baseline. Timing covers in-process CPU execution, excluding compiler
and process startup. Guard cost belongs in the residual timing.

## Reproduce

Use the project's LLVM 18 toolchain and pinned CPython 3.13.16:

```sh
python3 tools/regex_specialize.py '(\d{4})-(\d{2})-(\d{2})' \
  --output bench/regex_date_generated.py
./pystachy build bench/regex_specialized.py -o build/regex-specialized
./build/regex-specialized check
make regex-specialization-check
python3 tools/regex_specialize_bench.py --executable build/regex-specialized \
  --rounds 7 --repeats 20000 --output build/regex-value-measurements.json
```

The checked-in example is deterministic. The benchmark rotates VM, adapter,
guarded residual, unguarded concrete and CPython's actual C-engine `findall`.
CPU affinity is inherited by all child processes; the runner validates every
checksum and records interpreter/toolchain versions, source/executable hashes,
raw samples and ranges. Pass `--cpu` to choose another available processor.

## Measurements and checks

On a shared AMD EPYC 9V74 host, pinned to CPU 0, LLVM 18.1.3 and CPython 3.13.16,
each sample extracts from five ASCII log-like subjects 20,000 times. All modes
return the same tuples and consume them into checksum 558,860,000. The second
seven-round rotated run measured:

| Implementation | Median CPU seconds | Minimum–maximum |
|---|---:|---:|
| Ordinary native fixed-arity VM | 0.429 | 0.363–0.594 |
| Native portable adapter (`finditer` + groups) | 0.541 | 0.399–0.558 |
| Native guarded residual | 0.244 | 0.224–0.287 |
| Native unguarded concrete residual | 0.206 | 0.171–0.278 |
| CPython C-engine `findall` | 0.267 | 0.234–0.412 |

The guarded residual is about **1.8× faster than the VM control**. The unguarded
control establishes useful value-dependent headroom, and the guarded helper
retains most of it. CPython's range overlaps the guarded native range, so this
does not establish a reliable improvement over CPython. The earlier seven-round
run measured 0.434/0.235 seconds (1.85×) for VM/residual; the matching algorithm
is unchanged between runs. The final rebuild includes clarified contract comments
and the runner hash in provenance. Both raw reports are in
[`bench/results`](../bench/results/).

Eleven dedicated tests pass, including exhaustive ASCII category predicates,
120 deterministic randomized date subjects, nested/empty captures, fixed arities
two through five, Unicode fallback, bounded positions, same-arity pattern/flag
misses, unmatched captures, empty-match fallback, bytecode mutation and rejected
generation shapes/budgets. Native checks run generated shapes through JIT and the
date workload through JIT/AOT and per-allocation GC stress, with IR verification.
Independent review caught and corrected Unicode whitespace U+001C–U+001F and
empty-repeat expansion. The existing targeted regex/fnmatch/textwrap/HTML corpus
passes 38 JIT/AOT checks, and `re_probe`'s five deterministic engine limits and
Ruff pass. No compiler or runtime change requires a new local bootstrap; full
GitHub verification runs for the draft, including the new check in its benchmark
group. Passing local checks do not imply GitHub CI has finished.

The date scanner is a bounded component workload. It does not establish an HTML,
fnmatch, textwrap or agent-harness speedup, and it does not replace the general
backtracking engine. It establishes whether ordinary native compilation leaves
useful value-dependent work for a small residual program to remove.

## What remains

Runtime feedback could select repeated pattern values and request bounded residual
versions, once the headroom is established. A richer pattern compiler would need
backtracking and capture semantics, mutation invalidation, code-size limits and a
profitability policy. Dynamically different capture arities still require a shared
tagged representation or tuple/container unions; receiver guards cannot supply
that ABI. Bytes patterns and lazy match iterators remain separate runtime and
language work.

Related: [#345 regex performance](https://github.com/den-run-ai/pystachy/issues/345),
[#376 scalar dynamic execution](https://github.com/den-run-ai/pystachy/pull/376),
[#382 finite scalar unions](https://github.com/den-run-ai/pystachy/pull/382),
and [#384 receiver feedback](https://github.com/den-run-ai/pystachy/pull/384).
