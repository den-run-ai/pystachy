# PyJS-inspired Pystachy prototypes

Measurement snapshot based on Pystachy `04860a83618e744c6f461761b6ee7fdbbe21f985`.
The inspected PyJS reference is `be359569398b4cb3c3abb9d31ebd4f1bed88abe2`.
The experiments were completed before publication. This research branch preserves
the combined evidence; the two compiler changes are submitted independently.
Recorded `unpublished` and `local_only` fields describe the measurement stage.
The research branch itself is not proposed for merge.

## Results

Two prototypes have demonstrated benefits: a small extension to private optional
scalar optimization, and ASan instrumentation for generated AOT/extension code.

### 1. Remove optional boxes at dictionary lookups

The existing `unionslots` pass already splits eligible optional locals into a
presence flag and scalar payload. It previously retained the box returned by
`dict.get(key)`. The prototype recognizes a bounded case: a default-None lookup
whose result is stored once into a private numeric local and used only for
presence tests and numeric reads.

The compiler performs the original dictionary lookup once, tests its entry index,
and snapshots the payload immediately through `pys_dict_val_or_zero`. A missing
entry supplies zero bits without accessing dictionary storage. The separate
presence flag distinguishes absence from zero, False, negative zero, and NaN.
Hash/equality callbacks and exceptions keep their original position; later
dictionary mutation cannot change the saved result.

| AOT workload | Current main median | Prototype median | Main / prototype |
|---|---:|---:|---:|
| Rank lookup minimum, complete process | 77.57 ms | 59.45 ms | **1.30×** |
| BPE encoding, per corpus | 10.30 ms | 9.80 ms | **1.05×** |
| Complete BPE driver | 1.880 s | 1.802 s | **1.04×** |
| Direct-minimum control | 10.05 ms | 10.04 ms | **1.00×** |

Linux x86-64, LLVM 19.1.7, CPython 3.13.16. These are incremental comparisons with
current Pystachy, not comparisons against PyJS or against older Pystachy releases.
Two warmups and nine alternating pairs were pinned to one CPU. This task paused
other builds/tests during timing; the host may be shared. The candidate was
faster in all nine pairs for rank lookup, BPE encoding, and the complete BPE
process. Ranges and every raw sample are in [the timing record](results/llvm19-aot.json).
The approximately 5% encoding result is a modest local improvement, not a
general tokenizer performance claim. Training and decoding fluctuations are not
attributed to this change.

Every timed and warmup native sample matched its CPython reference. For BPE,
the existing adapted kernels first matched the pristine upstream kernels under
CPython; every native sample then matched all **130,147 output bytes** describing
the vocabulary, tokens, decoded bytes, and decoded text. The BPE workload trains
a 1,024-token vocabulary on the existing pinned Frankenstein introduction and
performs 100 encodes and 100 decodes. The rank loop makes 9.6 million visits,
with 80% dictionary hits, over 30,000 rounds.

### Separate JIT measurements

The lookup change adds a small runtime read after the dictionary search. Because
JIT does not inline that runtime code, its performance was measured separately
using fresh JIT compilation, warm private runtime caches, and disabled native
program caching. Both compilers were hosted by the same CPython. Two warmups
and seven alternating pairs were pinned to one CPU; all 42 timed samples and
12 warmups matched complete CPython output. The microbenchmark adds timers at
its entry points; its kernel functions remain byte-for-byte unchanged.

| JIT workload | Current main median | Prototype median | Main / prototype |
|---|---:|---:|---:|
| Rank lookup kernel, execution only | 149.31 ms | 112.42 ms | **1.33×** |
| Rank lookup, complete fresh process | 434.30 ms | 391.97 ms | **1.11×** |
| BPE encoding, per corpus | 10.568 ms | 10.647 ms | **0.993×; inconclusive** |
| Complete fresh BPE process | 4.471 s | 4.438 s | **1.007×; inconclusive** |

Rank execution and complete-process time improve in all seven pairs. The rank
process time outside the measured kernel is essentially unchanged (278.92 vs
278.40 ms median); this is not evidence of faster compilation. JIT BPE encoding
and complete-process time improve in only three of seven pairs, so **no JIT BPE
speedup is established**. The direct-minimum control also fluctuates widely and
has no consistent gain. One candidate BPE sample slows all stages and process
overhead together; it remains in the record, with no samples excluded. These
shared-host observations support a bounded rank-loop gain and leave JIT BPE
performance inconclusive. See [all JIT samples and timers](results/llvm19-jit.json).

### Allocation evidence

Separate binaries built with `-DPYSTACHY_PROFILE_DATA` measured C-runtime
allocation requests. Their timings are excluded from the table above. Both
variants used identical `argv[0]`, so binary-name lengths cannot alter byte
counts. These counters describe allocation requests and managed heap size,
not total process RSS or all memory traffic.

| Workload / measure | Main | Prototype | Reduction |
|---|---:|---:|---:|
| Rank loop allocation requests | 7,680,036 | 36 | **7,680,000 temporary boxes** |
| Rank loop requested allocation bytes | 115,227,194 | 27,194 | 115.2 MB |
| Rank loop peak managed heap | 33.5 MiB | 1.3 MiB | 96% |
| Complete BPE allocation requests | 90,586,326 | 85,726,926 | **5.36%** |
| Complete BPE requested allocation bytes | 3,912,662,423 | 3,839,771,423 | 1.86% |
| Complete BPE peak managed heap | 38.7 MiB | 38.7 MiB | No change |

The direct-minimum control has exactly the same seven allocation requests and
2,794 requested bytes in both variants. See [allocation records](results/allocations.json).

Static inspection found that **only `bpe_encode` changes among 220 functions**.
It loses one `dict.getbox` call site, gains one lookup and one guarded payload
read, and replaces the private pointer slot with scalar slots. The other 219
functions are byte-identical. The generated module grows by 323 bytes after
normalizing only the documented checkout-path string difference. The executable
size remains 429,056 bytes. These static facts are distinct from the dynamic
allocation counts.

The implementation adds one internal runtime entry, with no public ABI or object
layout change. Compiler/runtime core changes total 77 inserted and nine deleted
lines. Escaping, copied, identity-sensitive, phi-produced, or generator values
keep their boxes. Non-None defaults and programs using dynamic Any or promoting
integers retain the old path. `PYSTACHY_OPT=-unionslots` disables this optimization.
Removing an allocation can delay a threshold-triggered collection, as with
existing allocation optimizations.

### 2. Instrument generated user functions with ASan

`PYSTACHY_CFLAGS=-fsanitize=address` now instruments generated AOT user functions
and CPython extension functions before linking them with the already-instrumented
runtime. Ordinary builds keep their previous commands. `ir` and `build --emit-ir`
still expose the original frontend IR.

The new independent probe poisons one numeric-list element through ASan's public
API, reads it from generated Python-loop code, and unpoisons it before runtime
cleanup. Actual current-main AOT builds silently read it at both O0 and O2.
The new instrumentation reports `AddressSanitizer: use-after-poison`, with the
expected eight-byte read.

On primary LLVM 18.1.3, all seven instrumented fault configurations detect the
read, while all seven matched controls omitting only user instrumentation miss
it. Twenty valid controls pass, including GC stress. This is evidence of a
coverage improvement, not a newly discovered production memory bug.

Review exposed an ASan constructor COMDAT collision when another independently
sanitized C object appeared first in native link order. The final prototype
consistently disables constructor COMDAT grouping for separately instrumented
owned modules. Regressions cover both native link orders at O0 and O2. The
existing runtime/JIT/constructor suite also passes, as do eight final LLVM 18
generator/finally configurations against CPython.

**Limits:** JIT still instruments the runtime only. The allocator's arenas have
no new per-object redzones or quarantine, so this is not complete bounds or
reclaimed-object detection. ASan's fake stack must remain disabled as documented
for Pystachy's collector. No CI jobs were added; the sanitizer test remains in
the existing discovery pattern.

### 3. Additional typed/dynamic boundary coverage

Three original programs exercise union tags and exactly-once effects; list
aliases across target/index/RHS rebinding and exception joins; and a captured
Any rebound by a callback after a float guard. Their 18 initial checks
already pass on main. They add regression coverage and did not discover a new
boundary bug. The lookup prototype also includes independent reentrant-key
tests covering mutation and exceptions inside hashing/equality, plus saved
results read after the dictionary is cleared.

## Validation and remaining scope

The combined implementation at `ce1445674f57d72005383947cdd61c3c81fbdb39`
passes a fresh three-stage native bootstrap on LLVM 18.1.3: all stages produce
identical compiler IR (893,716 lines) and identical runtime IR (21,100 lines).
The integrated native compiler emits the same 220 BPE function bodies as the
measured optimization prototype; its C runtime is also byte-identical to that
prototype's runtime.

- `make check-fast`: 659 tests passed, 16 skipped; Ruff and mypy over 56 source
  files pass. Fifteen skips are optional Lean kernel integration checks; the
  remaining opt-in real-build retained-IR check was then enabled and passed.
- Explicit retained-IR native checks: 10/10 pass, including failed builds that
  must preserve an earlier retained artifact.
- Native focused suite: **356/356 JIT/AOT checks** across 178 optimization,
  optional-value, and new boundary programs.
- Per-allocation GC stress: **16/16 JIT/AOT checks** across the two new lookup
  fixtures, three existing optional-scalar fixtures, and three boundary fixtures.
- The implementation's separate tests also cover O0, disabled-pass controls,
  reentrant callbacks, ASan faults, and independent native link orders, as
  recorded in the linked JSON evidence.

See [combined qualification](results/qualification.json),
[sanitizer checks](results/asan-checks.json), and
[static BPE comparison](results/bpe-ir.json).

Primary LLVM 18.1.3 runtime signature/effect checks pass on both base and
prototype: 671 and 672 entries respectively, 70 exception classes, and 193
subset-runtime functions. An initial LLVM 19 checker run reported the same 57
findings on both trees; these do not reproduce on the primary toolchain. Both
the failed and successful records are retained. Performance measurements remain
explicitly LLVM 19 measurements; validation on LLVM 18 is separate evidence.

No full `make verify`, full-corpus `irsame`, release CI, or macOS/ARM validation
was performed. This is a measured prototype, not a merge-ready release claim.

## Licensing and scope decisions

PyJS's root license at the inspected commit is
[BSD-3-Clause](https://github.com/pyjs/pyjs/blob/be359569398b4cb3c3abb9d31ebd4f1bed88abe2/LICENSE).
Some runtime material has separate CPython or Unicode provenance. **No PyJS
implementation, tests, workloads, CPython-derived runtime material, or Unicode
data was copied into these changes.** The implementation and regression cases
are independently authored extensions of Pystachy's existing mechanisms. This
is not a clean-room claim: the external source was inspected for ideas and
comparison. [Provenance](results/provenance.json) lists the inspected material.

Benchmark inputs were reused from Pystachy's already attributed optional-scalar
and byte-BPE studies. Existing third-party notices and the upstream BPE
provenance remain unchanged. There is no new third-party dependency.

The performance prototype is an extension to the existing local optional-slot
pass. It does not implement interprocedural lifetime summaries or unboxed
optional return/field ABIs. General reference-bearing allocation elision has a
collector-root risk; simple reference-free objects already benefit from LLVM
elision. Async support, richer host schemas, and portability changes would
need larger contracts and separate consumers. The selected work offered
smaller changes with directly demonstrated benefits.

## Reproduce

Use a clean base checkout at `04860a83618e744c6f461761b6ee7fdbbe21f985` and a
checkout of this measured prototype. `PROTO_BASE`, `PROTO_CHANGED`, `PROTO_WORK`,
`PROTO_LLVM`, and `PROTO_PY` below name the base checkout, prototype checkout,
private output directory, complete LLVM bin directory, and CPython 3.13.16.

```sh
for stage in prepare measure; do
  "$PROTO_PY" "$PROTO_CHANGED/bench/pyjs_prototypes/compare_optional_lookup.py" "$stage" \
    --base "$PROTO_BASE" --changed "$PROTO_CHANGED" --bpe "$PROTO_BASE" \
    --workdir "$PROTO_WORK" --llvm "$PROTO_LLVM"
done
"$PROTO_PY" "$PROTO_CHANGED/bench/pyjs_prototypes/profile_optional_lookup.py" \
  --base "$PROTO_BASE" --changed "$PROTO_CHANGED" \
  --workdir "$PROTO_WORK" --llvm "$PROTO_LLVM"
```

The controller pins workload hashes, uses private caches, checks binary hashes,
checks complete output before accepting each sample, and retains all results.
Build timing includes cold/cache effects and is not used as compiler-speed
evidence. Separate profiling builds count allocations; ordinary binaries supply
the performance measurements.

For the separate JIT measurement, use another private output directory in
`PROTO_JIT_WORK`. Preparation reads the pinned source copies from the AOT
controller's `PROTO_WORK`, checks CPython equivalence, and warms runtime caches.
Both compiler checkouts must be clean. JIT process timings include compilation;
inner timers isolate kernel execution.

```sh
for stage in prepare measure; do
  "$PROTO_PY" "$PROTO_CHANGED/bench/pyjs_prototypes/compare_optional_lookup_jit.py" "$stage" \
    --base "$PROTO_BASE" --candidate "$PROTO_CHANGED" --inputs "$PROTO_WORK" \
    --workdir "$PROTO_JIT_WORK" --llvm "$PROTO_LLVM" --python "$PROTO_PY"
done
```

For the sanitizer regression, with matching LLVM and ASan runtimes installed:

```sh
cd "$PROTO_CHANGED"
PYSTACHY_LLVM="$PROTO_LLVM" "$PROTO_PY" -m unittest discover \
  -s tools -p test_runtime_asan.py -v
```

The locally tested standalone implementation commits are `05f3171f7bbb6068880af46d9e64cc5be2a0c413`
(optional lookups) and `3407632d010390bc1b5977c7bc72950da147c152` (ASan). Each is
based directly on the measured main revision and is submitted separately.
This report retains the original local qualification; current remote checks are
tracked on the individual pull requests.

Published implementation trees match those local commits exactly; see the
[publication record](results/publication.json) for remote commit identities.
