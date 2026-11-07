# Byte-BPE across CPython, Cython, mypyc, PyPy and Pystachy

## Result and scope

On this workload, **Pystachy AOT is 4.84× faster at training, 2.89× at encoding
and 3.30× at decoding than the original CPython implementation**. It is faster
than the tested Cython and mypyc variants in all three stages. Against PyPy,
Pystachy is about 1.95× faster at training and 1.94× at decoding; **PyPy has the
better encoding median**. This is a comparison of one educational byte-BPE
implementation, with its Python containers and merge algorithm preserved.

These measurements were taken on **7 November 2026 UTC**, beginning at
`2026-11-07T04:04:04Z`, against [the #1107 port at
3d0f56d8](https://github.com/den-run-ai/pystachy/tree/3d0f56d82e3f7e3e0799d37e014f73391913f1ca/examples/byte_bpe).
Compiler/runtime/library sources match main at
`f7103067545b43cdcd8ce20dc66b1571425b3a8d`. The original archive carried a
November 6 filename; the raw timestamps identify the actual runs. This warmed
protocol differs from [the earlier port measurements](../README.md); their
numbers are retained as a separate experiment, not a before/after compiler gain.

This research contributes partial evidence to [#1012](https://github.com/den-run-ai/pystachy/issues/1012)
and [#361](https://github.com/den-run-ai/pystachy/issues/361). It does not establish
performance for other tokenizers, larger corpora, production Rust tiktoken, a
Cython implementation rewritten around C containers, or all workloads supported
by any of these runtimes. No compiler change is proposed here.

## Primary comparison

Median milliseconds per operation; five interleaved process samples per mode.
RSS is the median sampled main-process high-water mark over the complete warmed
command, in MiB. Raw samples and ranges are in [comparison.json](comparison.json);
the mechanically derived table is [summary.csv](summary.csv).

| Runtime/source | Train, ms | Encode, ms | Decode, ms | RSS, MiB |
|---|---:|---:|---:|---:|
| CPython, original | 4,208.356 | 32.985 | 0.609 | 14.64 |
| CPython, Pystachy-adapted source | 4,287.428 | 37.056 | 0.631 | 14.80 |
| Cython, original | 2,567.444 | 22.396 | 0.470 | 17.11 |
| Cython, modest scalar annotations | 2,558.948 | 21.801 | 0.471 | 17.09 |
| Cython, Pystachy-adapted source | 2,701.874 | 24.762 | 0.485 | 17.33 |
| mypyc, one required annotation | 2,934.504 | 21.961 | 0.546 | 17.13 |
| PyPy, original | 1,698.083 | 10.565 | 0.359 | 112.61 |
| Pystachy AOT, port | 870.192 | 11.401 | 0.185 | 39.77 |

The original CPython baseline determines the headline gains. The adapted
CPython baseline stays separate: materializing iterator inputs changes its
allocation cost. The Cython control using that same port makes this effect
visible without attributing it to Pystachy's compiler.

PyPy's encoding median is about 8% better than Pystachy's. Their observed ranges
overlap: **8.694–11.780 ms for PyPy; 11.382–12.653 ms for AOT**. Five shared-host
samples do not establish a precise population difference or prove JIT
convergence. A separate longer-warmup diagnostic below also favors PyPy, with
its different driver and inlining context stated explicitly.

### Source adaptations and tool versions

| Mode | Source/build contract |
|---|---|
| Original CPython and PyPy | Exact class/function text from the pinned upstream file; omit only the unused pyperf runner/setup and expose the common pattern constant. |
| Cython original | Compile the pristine upstream module with its existing annotations. |
| Cython scalar | Add `import cython` and two `cython.locals` decorators for loop indices/token count and a byte local; retain Python containers and enable bounds, overflow, wraparound and initialized checks. |
| mypyc | Add only `stats: collections.Counter[tuple[bytes, bytes]] = collections.Counter()` to satisfy the compiler's required annotation. |
| Adapted CPython, Cython and Pystachy | Use the exact #1107 port, including its documented container annotations, iterator materialization and positional decoding arguments. |

CPython **3.13.16** is the common interpreter for the baseline and extension
builds. Compiler packages are **Cython 3.3.1**, **mypy/mypyc 2.4.1** and
**setuptools 80.9.0**, with **GCC 13.3.0, `-O3`**. PyPy is **8.0.1, Python
3.11.17**. Pystachy uses **LLVM 18.1.3**. The
[comparator manifest](comparator-manifest.json) retains source and native module
hashes, build commands and flags. Every compiled comparator was loaded from a
native `.so`; a launcher assertion rejects a Python fallback. A tiny pyperf
stub serves the upstream module's unused runner import, outside measured work.

The source is Shantanu Jain's pyperformance 1.14.0 tokenizer, derived from
OpenAI's educational tiktoken code. The existing [upstream provenance](../../upstream/provenance.json),
[MIT license](../../../../bench/pyperformance/LICENSE),
[authors](../../../../bench/pyperformance/AUTHORS) and
[notices](../../../../THIRD_PARTY_NOTICES) apply to the preserved and adapted
sources. The Cython/mypyc variants are deliberately small adaptations, not a
claim about the maximum performance attainable with either compiler.

### Timing and correctness protocol

The host was Linux x86-64 on an AMD EPYC 9V74, pinned to CPU 0, with other work
possible on the shared host. The unchanged Frankenstein excerpt contains
**31,206 UTF-8 bytes**. Vocabulary size is **1,024**; the trained model produces
**10,335 corpus tokens**.

Each process performs two training warmups, then times one fresh training run;
the first and second training times are retained separately. It then performs
20 encoding warmups and times 50 encodings, followed by 100 decoding warmups and
200 timed decodings. The run order rotates between rounds and reverses on
alternate rounds. Imports, file I/O, compilation, printing and output validation
are outside the stage timers. Whole-command time includes all warmups and is
not single-query latency. This is a specified warmed protocol, not proof that
every runtime has reached its eventual steady state.

All **45 primary process samples** (including the native tuple variant reported
separately below) match the original CPython oracle byte for byte: the complete ordered
vocabulary, complete token list, decoded bytes and decoded text. The
[130,147-byte oracle](full-output-oracle.txt) has SHA-256
`5107a185eeddfadaf261c250991f819e14ccfb8b85e41f0fd916785910df152e`.
Separate fixtures cover all 256 byte values, unseen Unicode, whitespace,
frequency ties, overlapping pairs, malformed UTF-8 replacement and rejections.
Native fixtures also pass collection at every allocation. PyPy's Python 3.11
empty-`max` wording is an accepted version-specific alternative in the fixture;
traceback formatting is not claimed identical. See
[native/interpreter correctness](correctness-final.json) and
[comparator correctness](comparator-correctness.json).

The runner cleans inherited Pystachy/PyPy settings, fixes `PYTHONHASHSEED=0`,
disables native program caching and records source/tool hashes, overrides,
affinity and shared-host load. RSS samples Linux `VmHWM` approximately every
5 ms after the requested command is installed, with PID-namespace checks;
it excludes child processes and can miss a brief final peak. The retained
`wait4` peak may include the launcher's pre-exec high-water mark. PyPy RSS
includes its warmed JIT; native-driver JIT RSS includes the compiler.
Comparator build and cold-start costs were not measured in repeated, interleaved
comparisons here; single build records and warmed whole-process times do not
answer those parts of #1012.

## Separate experiments and limits

These series are not pooled with the primary comparison.

### GC threshold and JIT inlining

[secondary.json](secondary.json) contains three interleaved process samples per
mode under the same warmup protocol:

| Variant | Train, ms | Encode, ms | Decode, ms | RSS, MiB |
|---|---:|---:|---:|---:|
| Native-driver JIT, default | 989.182 | 13.795 | 0.176 | 116.81 |
| JIT, `PYSTACHY_JIT_INLINE=100000` | 977.577 | 13.673 | 0.181 | 118.68 |
| AOT, `PYSTACHY_GC_MIN=8` | 893.492 | 10.108 | 0.149 | 14.89 |

Raising the inlining budget gives **no reliable execution improvement** here.
Whole warmed commands take medians of 5.391 s and 5.882 s for the two JIT modes;
these include compilation and all repeated work, not isolated LLVM time.

The 8 MiB collection threshold brings AOT RSS down from about 39.8 to 14.9 MiB.
The default-AOT and GC8 samples came from different series, so their timing
differences cannot establish a GC cost or speedup. This supports workload-specific
memory tuning; it does not justify changing the global default.

### Removing a comparison tuple

A source diagnostic replaces `(word[i], word[i + 1]) == most_common_pair` with
two short-circuit byte comparisons. For this kernel, exact builtin bytes and
proved-valid indices preserve behavior; this is not a valid general rewrite
for arbitrary objects with side effects. Complete-state and GC-stress checks
pass; the [variant manifest](scalar-tuple-manifest.json) records its identities.

Optimized native inspection confirms removal of **5,515,789 comparison-tuple
allocation-site executions per training**. Yet the training median changes only
from 870.192 to 832.887 ms: ratio of medians **1.045×**, median paired ratio
**1.009×**, with individual pairs both faster and slower. The result is
**inconclusive**, not a demonstrated optimization win. Scalar bytes equality
still uses generic runtime equality. Fewer allocations alone do not determine
elapsed time.

### Encoding decomposition and longer warmup

A separate driver measures reusable intermediate phases; three processes per
mode, 20 warmups and 50 timed repetitions per phase. All complete six-line
witnesses match, including pretokenized and UTF-8 word lists. Medians from
[encoding-phases.json](encoding-phases.json), in ms:

| Phase | CPython | PyPy | Pystachy AOT |
|---|---:|---:|---:|
| Regex splitting | 1.046 | 1.189 | 1.046 |
| Pre-split word UTF-8 conversion and list collection | 0.301 | 0.0354 | 0.936 |
| Precomputed byte-word merge and token extension | 30.629 | 7.125 | 9.174 |
| Full encoding control | 28.770 | 8.812 | 11.871 |

**The phases are nonadditive.** They reuse different intermediates and have
different allocation/JIT history. This driver calls `bpe_encode` at two sites;
its native binary retains a shared uninlined function, unlike the primary
driver's inlining opportunity. Regex is not demonstrated as the source of the
native encoding gap in this diagnostic.

Using that same decomposition binary, a further full-encoding-only series runs
200 warmups and 200 timed operations in three alternating PyPy/AOT pairs.
[warmup-sensitivity.json](warmup-sensitivity.json) records PyPy **9.463 ms**
(9.261–10.194) and AOT **11.742 ms** (11.738–15.060). PyPy wins all three pairs;
the ratio of medians is 1.241×. Do not attribute the difference from the primary
matrix entirely to warmup, or treat this as proof of JIT convergence.

## Remaining performance work

[operations.json](operations.json) counts exact source operations on the full
corpus and validates the complete state. Native IR/disassembly inspection
confirmed that the named allocation/helper sites survive optimization. These
are source-operation and site-execution counts, **not allocator-instrumented
totals, allocated bytes, live heap, collision counts or CPU-time shares**.
The [native-site excerpts](measured/native-sites.txt) retain the relevant
instructions and binary identities without full disassembly dumps.

| Target | Evidence | Next experiment |
|---|---|---|
| Literal UTF-8 codec resolution | 6,460 explicit `encode("utf-8")` calls per corpus. `pys_str_encode` resolves the codec before the existing no-copy UTF-8 path; normalization and alias construction repeat. | Specialize a known literal or add an exact-name fast path; preserve aliases/errors and measure the complete encoder. The 0.936 ms isolated phase includes loop/list work and is not the potential saving. |
| Optional integer boxes in encoding | 48,594 successful rank lookups and 29,215 minimum updates yield 107,024 scalar boxing-site executions. | Represent suitable `int | None` temporaries without heap boxes; validate observable identity/escape boundaries and measure full encoding. |
| Candidate bytes and iterator materialization | 82,362 candidate concatenation/lookups and 27,331 materialized zip scans per encoding. | Evaluate allocation-free typed lookup or iterator lowering, preserving Python evaluation and exception order. |
| Trainer Counter updates | 5,528,063 increments per training. Membership/read is already fused; the subsequent write still performs a separate probe. | Investigate fused updates through the typed Counter wrapper, with mutation/alias checks. |
| Trainer temporary containers | 9,922,560 pair-scan slices, 4,961,280 rebuilt word lists, and 11,043,852 tuple construction-site executions per training. | Measure scalar replacement and typed equality together; the tuple-only diagnostic above is insufficient evidence of a win. |
| Repeated algorithmic work | 768 complete pair recount/rebuild rounds; repeated scans/rebuilds in encoding preserve the upstream quadratic long-word behavior. | Treat incremental pair counts, compact token structures or repeated-word caching as separate tokenizer algorithms with merge-order and mutability tests. |

Bytes/string hashes are already cached, Counter membership/read is already
fused, and UTF-8 already has ASCII/surrogate-safe no-copy returns. The gaps
above concern work that remains around those optimizations. Relevant pinned
source: [codec resolution](https://github.com/den-run-ai/pystachy/blob/f7103067545b43cdcd8ce20dc66b1571425b3a8d/runtime.py#L1969),
[string encoding](https://github.com/den-run-ai/pystachy/blob/f7103067545b43cdcd8ce20dc66b1571425b3a8d/runtime.py#L2054),
[Counter](https://github.com/den-run-ai/pystachy/blob/f7103067545b43cdcd8ce20dc66b1571425b3a8d/lib/collections/__init__.py#L959)
and [the tokenizer](https://github.com/den-run-ai/pystachy/blob/3d0f56d82e3f7e3e0799d37e014f73391913f1ca/bench/pyperformance/bpe_tokeniser.py).
No Callgrind or sampled CPU profile was collected; no CPU-time attribution is
claimed from these counts.

## Language support rechecked

The five original port edits were reverted one at a time against the complete
driver. [language-probes.json](language-probes.json) retains the diagnostics.
These are frontend/IR probes; an accepted probe is not additional native API
validation.

| Probe | Result on the measured core |
|---|---|
| Remove `_decoder` field annotation | Rejects: field type cannot be inferred. |
| Use untyped `Counter()` | Rejects: element type is unbound. |
| Use `enumerate(zip(...))` without `list(...)` | Rejects: nested iterator composition unsupported. |
| Use `bytes.decode(..., errors="replace")` | Rejects the keyword; positional arguments work in the port. |
| Use `ranks = {}` without its annotation | Emits IR: this particular annotation is unnecessary in the complete kernel. |
| File-based `json.load` / `json.dump` | Rejects missing module attributes. |
| Annotated cached instance method | Rejects the decorator; the equivalent typed top-level cached function emits IR. |

Do not generalize the original five edits to five independently necessary
workarounds or claim all empty-dictionary inference is blocked. Persistence,
GPT-2 loaders and cached methods remain separate API work.

## Related PRs worth evaluating

This is a dated dependency assessment, not a claim that these unmerged changes
improve the measured kernels. None is stacked into this comparison.

| PR and reviewed revision | Relevance |
|---|---|
| [#1103](https://github.com/den-run-ai/pystachy/pull/1103), `8e51fe2b` | Program caching addresses repeat-launch cost. The earlier BPE consumer measured 3.028 → 1.249 s at older `706b47fa`; that evidence does not validate this newer head. |
| [#1108](https://github.com/den-run-ai/pystachy/pull/1108), `88a66bec` | Source attribution and allocation/copy counters could sharpen the next profile; no BPE speedup measured. |
| [#1095](https://github.com/den-run-ai/pystachy/pull/1095), `08963a31` | Atomic GC treatment of suitable union boxes may be relevant; it does not remove the demonstrated boxing sites. |
| [#1098](https://github.com/den-run-ai/pystachy/pull/1098), `a021ee24` | Text-read inlining concerns input I/O, which these stage timers exclude. |
| [#1122](https://github.com/den-run-ai/pystachy/pull/1122), `fb279daf` | Compiler-generated guarded callback specialization is a separate prototype; application-level BPE benefit is unmeasured. |

The practical sequence is to keep #1107 as the demonstration port, review
program-cache launch behavior independently, then use the attribution work to
choose one measured runtime/compiler optimization. No cache, GC-default,
callback-specialization or tokenizer-algorithm change is needed to publish
this evidence.

## Reproduction and evidence integrity

The [portable comparison harness](../../compare/README.md) builds fresh artifacts,
checks native module loading, validates the fixture and complete per-sample
state, and records commands, versions and hashes. It replaces machine-specific
paths from the original run with explicit interpreter/compiler/toolchain options.
Its smoke mode is for correctness, not a replacement performance measurement.

The [manifest](manifest.json) identifies the curated evidence. The
[historical source inventory](measured/README.md) explains the `.py.txt` inputs and minimal diffs;
absolute paths in those snapshots and raw JSON are historical records. They
are not commands to copy onto another machine. The original measured runner
accepted duplicate timing keys by overwrite; the portable runner rejects them.
An independent audit found all 45 original records have exactly the five unique,
finite, positive timing rows, so this parser hardening does not alter the
published numbers. New smoke/validation output is not pooled with those samples.

From the repository root, verify the preserved evidence without rerunning timers:

```sh
python3 examples/byte_bpe/results/runtime-comparison-2026-11-07/verify.py
```

The evidence retains the primary matrix, separate JIT/GC series, diagnostic
series, complete oracle, compiler/comparator identities, correctness records,
source diffs and language probes. It omits executables, virtual environments,
generated C/IR, duplicate corpus files and full disassembly dumps. Rebuilds and
new profiling should produce their own identified artifacts. The full compiler
verification matrix was not rerun for these research measurements; the new
runner's unit/smoke checks and PR CI are separate validation, not retroactive
benchmark samples.

### Publication checks

All nine primary modes passed the portable runner's fresh-build smoke, including
four compiled Cython/mypyc modules, PyPy, both native variants, complete-state
comparisons and the two native GC-stress fixtures. Subsequent review hardened
assertion/environment checks, interpreter identification and compiler-process
timeout cleanup. The final controller passed a separate CPython-original,
CPython-adapted and PyPy smoke and 13 contract/integrity tests.

The 30 existing byte-BPE/pyperformance controller tests, 14 workflow-limit tests,
11 repository-hygiene tests, complete `make lint`, staged whitespace checks and
relative documentation-link checks pass. The evidence verifier audits all 69
recorded process samples. Initial local lint/workflow invocations lacked the
LLVM setting and PyYAML in the bare interpreter; both pass with the configured
LLVM toolchain and pinned development environment. No full performance rerun,
optional-secondary smoke or full local `make verify` was performed for
publication. These checks add no CI jobs and no timing gate.
