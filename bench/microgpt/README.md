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

On 2026-10-17, compiler `d3fbfc6f5f6d5650f25ffc0d97be93b512f41a6f`,
CPython 3.13.16 and LLVM 18.1.3, on an AMD EPYC 9V74 Linux x86-64 host
(shared container, eight-core quota, 8 GiB memory limit). These are medians of
three fresh processes per tier: **100 training steps / 744 training tokens**,
then five generated names, with the original 1000-step learning-rate schedule.

| Tier | Training | Five-name inference | Process wall | Training speedup vs original CPython |
|---|---:|---:|---:|---:|
| Original CPython | 15.152 s | 260.6 ms | 15.640 s | 1.00x |
| Adapted CPython | 15.220 s | 280.2 ms | 15.928 s | 1.00x |
| Pystachy JIT | 0.908 s | 14.26 ms | 1.404 s | 16.69x |
| Pystachy AOT | 0.896 s | 13.45 ms | 0.924 s | 16.91x |

AOT is **16.99x** faster than the adapted CPython baseline for training and
**19.38x** faster than original CPython for inference. AOT training ranged from
0.884 to 0.945 seconds; its separately measured build took 1.802 seconds with
the runtime cache already available. JIT wall time includes its per-process
compilation. Phase medians need not sum to the median total.

All 12 processes passed elementwise checks of 25,252 floating-point values plus
exact document, vocabulary, token-count and generated-name checks. Adapted
CPython and JIT matched the original exactly; AOT's largest absolute difference
was `8.881784197001252e-16`. Generated names were `eri`, `eren`, `slrian`,
`deiyl`, `treiee`. A separate ten-step check on CPython 3.12.14 compared every
gradient (58,698 floating-point values per tier), and a two-step CPython 3.13
check passed with `PYSTACHY_GC_STRESS_PROGRAM=10000`.

The [recorded results](results/linux-x86_64-cpython313.json) retain each run's
phase totals, validation errors, provenance and reference digest. Rerunning the
controller produces the full reference vectors and individual step timings.
These are workload-prefix measurements, not a full 1000-step convergence claim.
Backward propagation remains the largest AOT phase (0.498 s median, about 56%
of training); forward computation takes 0.374 s and Adam 0.0255 s. No dedicated
profile yet attributes those costs to individual runtime operations.

A separate AOT run with `PYSTACHY_GC=stats` reported 50 collections, a 58.0 MiB
peak managed heap and 13.8 MiB live at the last collection, with the same
numerical checks passing. These are runtime heap statistics, not process RSS.
Its GC timing is retained only as a diagnostic because other compilation work
was running concurrently.

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
