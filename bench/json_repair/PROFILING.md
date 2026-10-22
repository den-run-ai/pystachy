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

## Reproduce

Build the probe using the checkout being measured, then select a mode and size:

```sh
PYSTACHY_PATH=ports ./pystachy build bench/json_repair/scaling.py -o /tmp/json_repair_scaling
PYTHONPATH=/tmp/json_repair_upstream/src python3.13 bench/json_repair/scaling.py escaped 1000 0
PYTHONPATH=ports python3.13 bench/json_repair/scaling.py escaped 1000 0
/tmp/json_repair_scaling escaped 1000 0

taskset -c 0 /tmp/json_repair_scaling escaped 1000 1
PYSTACHY_GC=stats /tmp/json_repair_scaling escaped 1000 1
PYTHONPATH=ports python3.13 -m cProfile -s tottime bench/json_repair/scaling.py escaped 1000 1
```

Choose an allowed CPU from `os.sched_getaffinity(0)` instead of assuming CPU 0.
Modes are `valid`, `comma`, `newline`, `unicode`, `escaped` and `logs`. The probe
checks the entire payload, object shape and log record types; witness lines must
agree across variants. The parity corpus provides the broader exact-log and
error-message checks. Keep ordinary timing separate from profiling and GC stats.
Escape-heavy inputs grow quadratically; start small and use an external timeout.
