# microGPT: native scalar-autograd training

This is Andrej Karpathy's dependency-free **microGPT**, not the PyTorch nanoGPT
repository. It trains the complete scalar-autograd transformer and samples names
on CPython and Pystachy's native JIT/AOT runtime. No tensor library, BLAS, embedded
CPython, pretrained checkpoint or algorithm replacement is involved.

The unmodified source does not compile today. The annotated adaptation keeps the
model, forward graph, recursive backpropagation, Adam updates and RNG sequence.
Both the original and the adapted program run under CPython in the benchmark,
so representation changes are visible separately from compiler performance.

## Source and data

- Upstream: https://gist.github.com/karpathy/8627fe009c40f57531cb18360106ce95
- Revision: `14fb038816c7aae0bb9342c2dbf1a51dd134a5ff`.
- Unedited copy: [upstream/microgpt.py](upstream/microgpt.py).
- Source SHA-256: `d47d88c2fd432c8ebdc1048beab7f7eb64ea7e0e664e11b812d72a6d95ebccee`.
- Adaptation: [microgpt.py](microgpt.py); changed areas carry port comments.
- License: [MIT](LICENSE), explicitly granted by the author in
  [comment 5999841](https://gist.github.com/karpathy/8627fe009c40f57531cb18360106ce95?permalink_comment_id=5999841).
  The gist has no separate license file; the included MIT text records that grant.

The measured dataset is the exact `names.txt` URL in the original source:
https://raw.githubusercontent.com/karpathy/makemore/988aa59/names.txt
Its SHA-256 is `0a30b5557f192f32ab962680889aac5f6fda0f4cecf40a6d0b5694f58ea8cc4d`.
It contains 32,033 names, giving 27 tokens including BOS and 4,192 parameters.
The dataset is supplied separately; the benchmark never downloads it. Custom
text datasets are accepted and identified by their recorded hash; the published
snapshot uses the exact file above.

## Reproduce

From the repository root, with the LLVM toolchain configured normally:

```sh
python3 tools/bench_microgpt.py --input /path/to/names.txt \
  --compiler './pystachy' --steps 100 --samples 5 --repeats 3 \
  --json build/microgpt.json

# Detailed numerical check: every gradient at every one of ten steps.
python3 tools/bench_microgpt.py --input /path/to/names.txt \
  --compiler 'python3 pystachy.py' --steps 10 --samples 3 --repeats 1 \
  --all-gradients --json build/microgpt-check.json

python3 -m unittest discover -s tools -p test_bench_microgpt.py
```

The controller instruments both sources identically. It retains `num_steps=1000`
for learning-rate decay even in a shorter measured prefix. Model dimensions stay
at one layer, width 16, context 16 and four heads; seed 42, document shuffle,
Gaussian parameter initialization and categorical sampling retain their order.
The adapted standalone script retains the original 1000-step/20-sample defaults
and requires `input.txt` in its working directory.

Every run checks all initial/final parameters, Adam first/second moments, all
losses, processed documents, token counts, vocabulary and generated names against
the original CPython source. Full gradient vectors are checked at the first and
last step, or every step with `--all-gradients`. The tolerance is `rtol=1e-9`,
`atol=1e-10`; the report retains maximum observed error. Unit tests independently
compare 26 small graphs, including sharing, ordered edges and every node's gradient.

Timers separate initialization, forward, backward, Adam and inference. They
exclude numerical snapshots and progress output. AOT build and whole-process
wall times are reported separately. Snapshot allocations can shift later garbage
collection work between phases, so phase times describe the instrumented workload.
JIT runs follow the AOT build and can reuse
the runtime cache. Repetitions rotate tier order. Timings are advisory on shared
hosts, and the benchmark imposes no performance threshold. Raw results include
source/data hashes, compiler revision, settings, timings and validation failures.

## Measured snapshot

On 3 November 2026, with v0.1.0-alpha.4 (`9c8bc746`), CPython 3.13.18 and LLVM 18.1.3, on a
shared 4-vCPU Intel Xeon @ 2.10 GHz VM, every process pinned to one CPU. These are medians of
three fresh processes per tier: **100 training steps / 744 training tokens**, then five
generated names, with the original 1000-step learning-rate schedule.

| Tier | Training | Five-name inference | Process wall | Training speedup vs original CPython |
|---|---:|---:|---:|---:|
| Original CPython | 9.813 s | 246.0 ms | 10.228 s | 1.00x |
| Adapted CPython | 9.241 s | 236.8 ms | 9.686 s | 1.06x |
| Pystachy JIT | 1.035 s | 15.32 ms | 1.354 s | 9.48x |
| Pystachy AOT | 0.933 s | 13.05 ms | 0.964 s | 10.51x |

AOT is **9.90x** faster than the adapted CPython baseline for training and
**18.85x** faster than original CPython for inference. AOT training ranged from
0.890 to 1.076 seconds; its separately measured build took 2.47 seconds with
the runtime cache already available. JIT wall time includes its per-process
compilation. Phase medians need not sum to the median total.

All 12 processes passed elementwise checks of 25,252 floating-point values plus
exact document, vocabulary, token-count and generated-name checks, and every tier
matched the original program exactly. Generated names were `eri`, `eren`,
`slrian`, `deiyl`, `treiee`. A separate ten-step check compared every gradient
(58,698 floating-point values per tier), and a two-step check passed with
`PYSTACHY_GC_STRESS_PROGRAM=10000`; both matched exactly as well.

The [recorded results](results/alpha4-linux-x86_64-2026-11-03.json) retain each run's
phase totals, validation errors, provenance and reference digest. Rerunning the
controller produces the full reference vectors and individual step timings.
These are workload-prefix measurements, not a full 1000-step convergence claim.
Backward propagation remains the largest AOT phase (0.503 s median, about 54%
of training); forward computation takes 0.392 s and Adam 0.038 s. No dedicated
profile yet attributes those costs to individual runtime operations.

A separate AOT run with `PYSTACHY_GC=stats` reported 46 collections, a 57.2 MiB
peak managed heap and 13.8 MiB live at the last collection. These are runtime
heap statistics, not process RSS.

The 17 October snapshot, at `d3fbfc6f` on another host with CPython 3.13.16, is on
[this page as of alpha.4](https://github.com/den-run-ai/pystachy/blob/9c8bc74648aa7c7e6a1b9d8f9dbbfeb1f2908ad3/bench/microgpt/README.md#measured-snapshot),
with [its results](results/linux-x86_64-cpython313.json). Its 16.9x training speedup is
not comparable with this table: that host's CPython took 15.152 s for the same training.

## Adaptations and remaining gaps

| Original construct | Adaptation | Remaining work |
|---|---|---|
| Conditional `urllib.request` download | Require an existing local input file | Native urllib/networking support is outside this benchmark. |
| Inferred recursive fields and empty captured/nested lists | Explicit concrete annotations and float gradient constants | Inference coverage; related #118/#246. |
| Variable-length child tuples containing `Value` objects | `list[Value]` children; scalar derivative tuples retained | Reference elements in runtime-length tuples ([#637](https://github.com/den-run-ai/pystachy/issues/637)). |
| `isinstance` coercion of either a scalar or `Value` | Concrete operators and explicit scalar boxes at the same graph positions | Nullable class templates (#582) and mixed reference/scalar unions (#9/#108). |
| `sum()` over values and generators | `value_sum`, preserving first reflected-add order | User-defined addition/reflected addition in `sum` ([#636](https://github.com/den-run-ai/pystachy/issues/636)). |
| Scalar-left multiplication/division | Equivalent explicit `Value` operations | Reflected arithmetic (#113). |
| Object `**` | Explicit `__pow__` calls | Bounded numeric-exponent support in [PR #638](https://github.com/den-run-ai/pystachy/pull/638); the benchmark works independently of it. |
| Two attention generators capturing rebound loop locals | Eager comprehensions with the same products and edge order | More precise capture/lifetime analysis. |

Changing child tuples to lists and two generators to lists changes allocation
behavior. The benchmark therefore reports adapted CPython as well as original
CPython. The adapter is deliberately specific to this model: its sums are
nonempty, and its concrete operator signatures do not provide the original
class's complete general-purpose scalar/object API.

## Direct tuple materialization research

The bounded experiment for [#898](https://github.com/den-run-ai/pystachy/issues/898)
compares main at `f7103067545b43cdcd8ce20dc66b1571425b3a8d` with compiler source
`1d452c39e6f9752fdfd521e74b0cfdfa8e86f7d1`. The benchmark adaptation is unchanged.
Derivative tuples are constructed in their final runtime-length representation
using `vtuple.make`, which retains native typed operands and has one semantic
result. Existing fixed tuples are read directly into the final representation;
compatible tuple displays can avoid constructing a fixed tuple first. Literal
constant tuples retain their existing identity path. `Value` nodes and their
child lists retain their graph representation.

The [structural report](results/direct-tuples-ir-linux-x86_64-2026-11-07.json)
counts static sites after Pystachy's typed-IR passes:

| Derivative-producing method | Fixed tuple allocations, before → after | Typed operations, before → after |
|---|---:|---:|
| `Value.__add__` | 1 → 0 | 32 → 27 |
| `Value.__mul__` | 2 → 0 | 43 → 29 |
| `Value.__pow__` | 2 → 0 | 32 → 24 |
| `Value.log` | 2 → 0 | 30 → 22 |
| `Value.exp` | 2 → 0 | 32 → 24 |
| `Value.relu` | 2 → 0 | 28 → 20 |

Each method still allocates its `Value` node and final derivative tuple. Its
`vtuple.from` call becomes one `vtuple.make`; `__add__` retains two reads from its
constant derivative tuple. These are static operation counts, not dynamic
allocation counts or allocated bytes. LLVM may already remove some fixed scalar
tuples. The minimal `return (x, x + 1.0)` example with result annotation
`tuple[float, ...]` changes from two fixed allocations plus `vtuple.from` to one
`vtuple.make`.

### Timing and numerical evidence

The 7 November 2026 follow-up ran on a shared AMD EPYC 9V74 host, pinned to CPU 2,
with CPython 3.13.16 and LLVM 18.1.3. It uses the same seed, exact dataset and
100-step / 744-token / five-name workload described above. Both compilers run
hosted under the same CPython; generated JIT and AOT programs execute natively.
The final AOT comparison builds both executables first, then runs five pairs of
fresh processes, reversing before/after order on alternate pairs. No other
coordinated compiler builds or tests ran during these pairs.

| AOT phase | Main median | Direct tuples median | Before / after |
|---|---:|---:|---:|
| Forward | 394.34 ms | 339.30 ms | 1.162x |
| Backward | 508.23 ms | 529.10 ms | 0.961x |
| Adam | 38.85 ms | 40.02 ms | 0.971x |
| Training total | 943.57 ms | 900.17 ms | 1.048x |
| Five-name inference | 13.45 ms | 12.83 ms | 1.048x |

Training ranges overlap: 0.895–1.028 s before and 0.799–0.982 s after. One of the
five pairs is slower after the change. Forward execution improves in the median,
while backward and Adam medians regress slightly; the measured overall training
difference is inconclusive at this sample size on a shared host. The structural
simplification is established independently of the timing result. No build-time,
allocated-byte, or full 1000-step convergence improvement is claimed.

All ten alternating AOT processes match the original CPython reference exactly:
25,252 floating-point values per process, plus exact documents, vocabulary,
token counts and generated names. Maximum absolute numerical error is zero.
The [alternating report](results/direct-tuples-alternating-linux-x86_64-2026-11-07.json)
retains execution order, every run's phase totals and comparisons, source and
binary hashes, build commands, and the small comparison driver's exact source.
Full reference vectors and individual step timers can be regenerated with the
existing controller.

Earlier [baseline](results/direct-tuples-before-linux-x86_64-2026-11-07.json) and
[candidate](results/direct-tuples-after-linux-x86_64-2026-11-07.json) reports each
run all four tiers three times; all 24 processes also match exactly. Their
exploratory training medians are 1.117 → 0.884 s for JIT and 1.086 → 0.809 s for
AOT. These reports ran in separate blocks, and another test briefly overlapped
the measurement window. The apparent 1.26x/1.34x gains are therefore not reliable
estimates; the alternating AOT follow-up above is the primary timing evidence.
The controller's snapshots can also shift later collection work between phases.

To reproduce the full four-tier reports, use the command in **Reproduce** with
`--compiler 'python3.13 /path/to/before/pystachy.py'` and then the corresponding
candidate path, retaining `--steps 100 --samples 5 --repeats 3`. To reproduce the
bounded alternating follow-up, use the driver stored in its report and replace
the recorded workspace/Python paths with local paths. Generate a full original
reference report first. To reproduce static counts, run in each checkout:

```sh
python3.13 tools/inspect_compiler.py bench/microgpt/microgpt.py \
  --output /path/to/new-inspection-directory
```

### Correctness checks for the changed representation

The final compiler reaches a three-stage native fixed point: 833,069 compiler
IR lines and 18,805 runtime IR lines, identical between stages. Twelve selected
CPython differential fixtures pass in both native JIT and AOT (24 runs), and six
of those fixtures also pass with collection at every program allocation (12
runs). They cover evaluation order and later-item exceptions, optional/bool
packing, checked and promoting integers, constant identity, existing tuple
aliases, pointer-valued operands, and retained graphs. Typed verification plus
`llvm-as` accepts 67 selected tuple programs including microGPT after updating
one expected allocation-call snapshot. `make check-fast` passes, including 194
typed-IR tests; `check-runtime` passes.

An initial broader IR comparison found two new acceptance failures caused by
using an operand's contextual type too eagerly: nullable concatenation and
comparison of differently typed tuples. Both were fixed by retaining soft hints
and requiring compatible element conversions, then retested in the focused
native suite. That earlier corpus comparison contains expected IR changes and
checkout-path differences and is not a successful final byte-equality gate.
