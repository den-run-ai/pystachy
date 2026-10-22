# json_repair typing and payload-size measurements

The lookahead cache has a fixed internal shape, so the port uses
`dict[str, tuple[int, int | None]]` instead of `dict[Any, Any]`. Recursive JSON
values and the returned log list retain dynamic storage. Typing the log list as
`list[dict[str, str]]` was rejected at the `Any` return boundary; copying it solely
to cross that boundary would complicate the port without an established benefit.

Measurements compare PR #847's `c7f985b6` with the cache annotation in `360a1c0a`,
using the same compiler/runtime sources, CPython 3.13.16 and LLVM 18.1.3 on a shared
Linux x86-64 AMD EPYC 9V74 host. Each process was pinned to CPU 0. Variants were
interleaved; [samples and identities](results/typing-and-scaling.json) are retained.
Input creation, exact result checks, process startup and compilation are outside
the measured repair loop. These are diagnostic workloads, not production traces.

## Typing result

- The mixed benchmark's executable text shrank from 263,533 to 254,947 bytes
  (3.3%). Internal cache lookups no longer need fully dynamic keys and values.
- Seven mixed-workload samples measured median 0.262 s before and 0.243 s after
  typing per 20,000 repairs. The baseline ranged from 0.221 to 0.305 s: this is
  **not a demonstrated throughput improvement** on the shared host.
- Both variants reported five collections and a 34.1 MiB heap peak. Collection
  time was 1.6/1.7 ms; GC was a small part of this particular workload.
- The expanded 645-case replay matched 645/645 on CPython and 644/645 in AOT,
  normally and with collection at every allocation. The sole AOT mismatch was
  the retained signed-64-bit integer limit. This measurement did not separately
  repeat JIT replay or the full repository verification matrix.

## Larger payloads expose a more important bottleneck

`scaling.py escaped N 1` repairs a malformed object whose string contains `N`
escaped newlines and a final sentinel. The complete repaired string is checked
before and after timing. This models one feature of LLM-generated code strings,
without claiming a representative failure frequency.

| Escaped newlines | Input characters | CPython upstream | Original AOT | Typed-cache AOT |
|---:|---:|---:|---:|---:|
| 500 | 1,512 | 25.2 ms | 7.75 ms | 8.49 ms |
| 1,000 | 3,012 | 101.8 ms | 30.4 ms | 39.8 ms |
| 2,000 | 6,012 | 370.1 ms | 115.0 ms | 124.3 ms |

These medians have only three samples per entry. The near-fourfold cost when
size doubles is the useful result; small differences between native variants
are inconclusive. CPython `cProfile` attributes 0.193 of 0.226 instrumented
seconds (85%) to `_rebuild_unmatched_opening_braces` in `parse_string.py`.
`_normalize_escape_sequence` calls it after each escape, and it scans the whole
accumulated string. This is quadratic work in upstream's algorithm. Native
execution shares that algorithm, although native instruction attribution was
not collected. An incremental update of brace and bracket state is a useful
follow-up; it needs careful tests for rewritten delimiters and nested escapes.

Other follow-ups supported by source inspection and these probes:

- `_scan_string_body`, `get_char_at` and `_append_string_content` lead the mixed
  CPython profile. Repeated immutable-string concatenation/slicing may add
  copying cost on long malformed strings. Measure allocations and native
  instructions before changing accumulation strategy.
- Valid JSON already uses the fast path. The large valid-string probe showed no
  established native advantage over CPython's C decoder; the original mixed
  workload's speedup does not apply to all inputs.
- The one-character `str.find` scanner candidate had no demonstrated additional
  gain on these six probes or the mixed workload: typed-only/combined mixed
  medians were 0.259/0.256 s over seven interleaved samples. Its usefulness should
  be judged on inputs that actually spend time in `skip_to_character`.

## Incremental escape-state follow-up

The escape normalizer now retains brace/bracket metadata when removing a
trailing backslash and updates it only for the decoded replacement. Removing a
backslash cannot change either field; decoded braces and brackets still do.
For the escaped-fragment probe, the old rebuilding loop visits exactly
`N * (N + 1)` prefix characters. The replacement performs no prefix rebuilds;
all append metadata work visits `3 * N + 3` characters. String concatenation and
slicing still copy growing prefixes, so this does not establish linear total
runtime.

[Paired samples and source hashes](results/incremental-escape-state.json)
compare the PR #847 source at `563ed6d5` with the one-file change, on CPython
3.13.16, shared Linux x86-64, pinned to CPU 0. Seven samples per variant were
interleaved, with complete output witnesses checked. Input creation, startup,
validation and compilation are outside the measured loop.

| Escaped fragments | Before | Incremental state | Ratio |
|---:|---:|---:|---:|
| 500 | 24.59 ms | 1.61 ms | 15.3x |
| 1,000 | 99.22 ms | 3.58 ms | 27.7x |
| 2,000 | 407.35 ms | 7.32 ms | 55.6x |
| 4,000 | 1,625.34 ms | 19.12 ms | 85.0x |

These are CPython measurements of synthetic malformed inputs. The valid JSON
control was essentially unchanged. The mixed workload's medians were 270.7
and 281.2 microseconds per ten records, with overlapping sample ranges;
no general throughput improvement is established. New native JIT/AOT timings
and GC-stressed execution are reported below.

The candidate matches all 645 replay cases on CPython 3.13.16. Separate
CPython 3.12 checks matched 214,841 metadata transitions and 60,000 malformed
API calls against the unchanged parser. The maintained native-corpus regression
checks 110 metadata transitions and records 88 public API outcomes, including
Unicode structural escapes, regex brackets, backslash runs, smart quotes and
streaming EOF. Its output is recorded with CPython 3.13.16.

## Native measurements of incremental escape state

Measured on 2026-10-22 with LLVM 18.1.3 and CPython 3.13.16 for bootstrap.
The baseline is `563ed6d5`; the candidate is `0b5e3ec6`. Both clean checkouts
use the same freshly bootstrapped compiler, with identical compiler, runtime
and library sources. Compiler and runtime three-stage IR fixed points pass
(665,141 and 18,709 lines respectively). Each variant uses its own port sources.
[Native samples, witnesses and source/binary identities](results/native-incremental-escape-state.json)
retain every sample, including outliers.

The host is shared Linux x86-64, AMD EPYC 9V74, with processes pinned to CPU 0.
Seven baseline/candidate pairs alternate execution order; no local builds or
tests run concurrently. Default optimization and GC are used. The benchmark's
internal timer excludes input creation, full output validation, process startup,
JIT compilation and AOT build/linking. All output witnesses match.

| Escaped fragments | AOT before | AOT incremental | Ratio |
|---:|---:|---:|---:|
| 500 | 8.91 ms | 0.90 ms | 9.9x |
| 1,000 | 32.78 ms | 2.45 ms | 13.4x |
| 2,000 | 132.86 ms | 8.30 ms | 16.0x |
| 4,000 | 569.97 ms | 22.11 ms | 25.8x |
| 8,000 | 1,947.00 ms | 31.49 ms | 61.8x |

| Escaped fragments | JIT before | JIT incremental | Ratio |
|---:|---:|---:|---:|
| 2,000 | 134.01 ms | 8.05 ms | 16.6x |
| 4,000 | 445.35 ms | 15.06 ms | 29.6x |

These are synthetic malformed-string results, not general application speedups.
The mixed workload (20,000 repairs, including checksum work) measured
234.62/235.65 ms before/after in AOT and 251.15/258.30 ms in JIT. Sample ranges
overlap in both modes, so neither a throughput gain nor a regression is
established. The valid JSON control also has overlapping sample ranges.

Separate whole-process GC probes, including input creation and validation,
report identical counts and heap peaks: 92 collections and 45.6 MiB for 8,000
escaped fragments; five collections and 34.1 MiB for the mixed workload.
These statistics do not measure total allocated bytes or establish reduced
allocation. Candidate-only AOT probes at 8,000/16,000/32,000 fragments take
30.43/70.48/256.59 ms (three samples each). Growing-prefix concatenation and
slicing remain; linear end-to-end scaling is not established.

Native correctness checks at the measured candidate:

- Five focused programs pass in JIT and AOT: **10/10** normally and **10/10**
  with `PYSTACHY_GC_STRESS_PROGRAM=1`. These cover the port API, scanner,
  incremental escape regression, and typed/dynamic JSON raw decoding.
- The 645-case port replay produces byte-identical output in baseline AOT,
  candidate AOT/JIT, and candidate AOT/JIT with collection at every allocation.
  Each matches **644/645**: only case 59's existing signed-64-bit overflow remains.
  The parity checker still exits 1; the failing case is not waived or changed.
- Full local `make verify` was not rerun. Hosted CI status is tracked in PR #848;
  focused native execution does not substitute for the complete required matrix.

## Reproduce

Build the probe using the checkout being measured, then select a mode and size:

```sh
PYSTACHY_PATH=ports ./pystachy build bench/json_repair/scaling.py -o /tmp/json_repair_scaling
PYTHONPATH=/tmp/json_repair_upstream/src python3.13 bench/json_repair/scaling.py escaped 1000 0
PYTHONPATH=ports python3.13 bench/json_repair/scaling.py escaped 1000 0
/tmp/json_repair_scaling escaped 1000 0

taskset -c 0 /tmp/json_repair_scaling escaped 1000 1
PYSTACHY_PATH=ports taskset -c 0 ./pystachy run bench/json_repair/scaling.py escaped 2000 1
PYSTACHY_PATH=ports ./pystachy build bench/json_repair/bench.py -o /tmp/json_repair_mix
taskset -c 0 /tmp/json_repair_mix 2000
PYSTACHY_GC=stats /tmp/json_repair_scaling escaped 1000 1
PYTHONPATH=ports python3.13 -m cProfile -s tottime bench/json_repair/scaling.py escaped 1000 1
```

Choose an allowed CPU from `os.sched_getaffinity(0)` instead of assuming CPU 0.
Modes are `valid`, `comma`, `newline`, `unicode`, `escaped` and `logs`. The probe
checks the entire payload, object shape and log record types; witness lines must
agree across variants. The parity corpus provides the broader exact-log and
error-message checks. Keep ordinary timing separate from profiling and GC stats.
For the paired native comparison, build each variant's probes in its own checkout
with the same compiler executable and explicit `PYSTACHY_HOME`/`PYSTACHY_PATH`.
Remove inherited optimization, GC and cache overrides. Run seven interleaved
pairs per workload and retain all samples; use the sizes and round counts in
the native results file. Escape-heavy inputs can still grow superlinearly;
start small and use an external timeout.
