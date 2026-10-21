# Native CPU nanoGPT

This example reuses Pystachy's [ndarray port](../ndarray/README.md) to run the
nanoGPT architecture as compiled typed Python. The executable needs neither
CPython, NumPy nor PyTorch. An optional [BLAS adapter](../ndarray/README.md#optional-native-blas-matrix-multiplication)
calls an LP64 CBLAS shared library directly; the scalar runner has no BLAS dependency.

The architecture follows [karpathy/nanoGPT](https://github.com/karpathy/nanoGPT)
at commit `3adf61e154c3fe3fca428ad6bc3818b27a3b8291`: learned token and position
embeddings, pre-layer-normalized transformer blocks, causal multi-head attention,
GELU MLPs, residuals, final normalization and a tied embedding/output projection.
This is a CPU float64, dropout-free port. It supports bias on/off, batches,
full-sequence logits, last-position logits and cross-entropy with ignored targets.

## Export and run

PyTorch is needed only for the offline exporter/reference check. Supply an existing
checkout of the pinned upstream model; the checker verifies its SHA-256 and never
downloads source or checkpoints. From the repository root:

```sh
python3 tools/check_nanogpt.py --upstream-model /path/to/nanoGPT/model.py \
  --torch-python /path/to/python-with-torch --export-only build/nanogpt-fixtures

export PYSTACHY_PATH="$PWD/examples/nanogpt:$PWD/examples/ndarray"
python3 pystachy.py run examples/nanogpt/run.py \
  build/nanogpt-fixtures/batched_bias.weights build/nanogpt-fixtures/batched_bias.input --full --loss
python3 pystachy.py build examples/nanogpt/run.py -o build/nanogpt
build/nanogpt build/nanogpt-fixtures/batched_bias.weights \
  build/nanogpt-fixtures/batched_bias.input --last
```

The exporter creates deterministic random fixtures for validation. It is not a
pretrained model downloader. Exported files can be copied to a machine without
PyTorch or Python and read by the standalone executable. The runner defaults to
`--last`; `--full` returns every position. With `--loss`, the loss covers the
returned positions. Replace `run.py` with `run_blas.py` to select the optional
`libblas.so.3` backend, with each block's bias folded into its BLAS product.
That library must provide the documented LP64 ABI. Ubuntu's default
`libblas.so.3` is the reference BLAS, 2.5 times slower than OpenBLAS on the
benchmark model below; [install OpenBLAS](../ndarray/README.md#optional-native-blas-matrix-multiplication)
to make it the provider.

For CPython comparison, set `PYTHONPATH` to the same example directories and run
`python3 examples/nanogpt/run.py ...`. The BLAS CPython twin additionally needs
`tools/rt_cpython` on that path; it copies lists and does not model native FFI cost.

## API and file format

`GPTConfig(n_layer, n_head, n_embd, block_size, vocab_size, bias)` and
`GPT(config, parameters)` construct a model. `forward(model, tokens, batch,
length, last_only=False)` uses scalar matrix products; `forward_with_backend`
accepts a compatible `matmul(a, b)` callback. Its optional last argument,
`linear_fn(x, weight, bias)`, computes each block's four biased projections
instead of the product followed by a bias pass: `ndarray_blas.linear` folds the
bias into its BLAS product, and `run_blas.py` passes it. Attention and the
output projection still use `matmul`. Tokens are flattened in batch-major
order. Outputs have shape `[batch, length, vocab_size]`, or
`[batch, 1, vocab_size]` for the last-position path. `cross_entropy` averages over
nonignored positions (`-1` is ignored); an entirely ignored batch returns NaN.

Weights use the versioned text format `PYSTACHY_NANOGPT_V1`: a magic line, six
integers in `GPTConfig` order (bias is 0/1), a tensor count, then each tensor's
`name rank dimensions...` header followed by its C-order floating-point values.
Parameter names follow upstream `model.py`; `lm_head.weight` is omitted because
it aliases `transformer.wte.weight`. The loader rejects missing/extra names,
incorrect shapes, nonfinite values and trailing content. Inputs have exactly
three lines: `batch length`, flattened token IDs, flattened target IDs.

## Validation and measurement

```sh
python3 tools/check_nanogpt.py --upstream-model /path/to/nanoGPT/model.py \
  --torch-python /path/to/python-with-torch --benchmark --warmups 1 --repeats 5 \
  --blas-library libblas.so.3 --json build/nanogpt.json
python3 -m unittest discover -s tools -p test_check_nanogpt.py
```

The optional `--blas-symbol` selects an explicitly named LP64 `dgemm` symbol.
It cannot detect or convert an ILP64 ABI. The checker binds the selected library
in a temporary module, without changing the example's default. Common BLAS thread
environment variables request one thread; verify the selected provider honors
them. Export/reference work, compilation, process wall
time, weight loading and warm operation timings are recorded separately.
`--fixtures` reuses a hash-checked export without importing PyTorch.

The checker compares every logit and the loss against the pinned upstream
PyTorch model in float64, for one-token, batched, multiple-head and bias-free
cases. Inference timings separate full forward plus loss from the upstream
last-position optimization. Normal tests include independent upstream numeric
references, causal-prefix and batch-isolation checks, tied-weight mutation and
malformed-file rejection; these pass JIT/AOT with GC on every allocation.

The checker's BLAS tiers pass `ndarray_blas.linear`. Without PyTorch,
`make blas-check` runs [`blas_parity.py`](blas_parity.py): the BLAS backend, with
and without the folded bias, against the scalar one for full and last-position
logits, the loss and every gradient, under CPython, JIT, AOT and GC stress,
after the adapter's own checks. CI runs it against Ubuntu's OpenBLAS and against
the reference BLAS.

## Native training

[`training.py`](training.py) supplies analytic backward kernels and AdamW. It
shares the forward implementation and caches activations, and accumulates both
uses of the tied token/output parameter into one gradient. For example:

```python
from driver import read_input
from model import load_weights
from ndarray_blas import linear, matmul
from training import AdamW, loss_and_grad_with_backend

model = load_weights("model.weights")
inputs = read_input("batch.input")
optimizer = AdamW(model)
for step in range(10):
    result = loss_and_grad_with_backend(
        model, inputs.tokens, inputs.targets, inputs.batch, inputs.length, matmul, linear)
    optimizer.step(result.gradients)
    print(step, result.loss)
```

Use `ndarray.matmul` (and no `linear`) for the scalar backend. The optional
`linear` computes only the forward projections; every backward product uses
`matmul`. Parameters and gradients must be whole contiguous arrays. AdamW
validates every gradient before any parameter mutation and applies weight decay
only to parameters with at least two dimensions, matching upstream grouping. A new gradient dictionary is returned per call.
All-ignored targets produce NaN loss and zero gradients; calling AdamW afterward
still applies its optimizer state and weight-decay rules.

The checker defaults to two successive training steps (`--training-steps 0`
disables them), comparing every gradient, updated parameter and both optimizer
moment vectors to upstream PyTorch. Tests also compare directional finite
differences across every parameter and reject invalid optimizer inputs. Timing
separates forward/backward from the optimizer. PyTorch lazily initializes moments
inside its first optimizer step; the native constructor initializes them before
the timer. First-step optimizer timings therefore include different setup work;
use the later step for a steady-state comparison. Two steps establish bounded
update parity, not training convergence or stable long-run throughput.

## Recorded CPU result

[Recorded data](results/native-cpu.json), collected 2026-10-17 UTC on a shared
AMD EPYC 9V74 host, includes every timing sample, checks and source hashes.
The model has 108,288 unique parameters: two layers, two heads, width 64,
context capacity 64, vocabulary 64, bias enabled, batch 2 and sequence length 16.
All paths use float64 and dropout zero. This is a small randomly initialized
model, not a pretrained GPT-2 throughput claim.

The compiler source is based on `cad7e042`, using LLVM 18.1.3, CPython 3.12.14
and PyTorch 2.14.1+cpu. The native BLAS path directly loads the LP64 OpenBLAS
0.3.30 shared library distributed in the host's SciPy installation; its config
reports SkylakeX and its thread-count query confirms one thread. SciPy and
CPython are not loaded by that native executable. The default `libblas.so.3`
on this host is a different, reference implementation and was not used for
these optimized timings. PyTorch uses its own CPU kernels, so this compares
complete implementations rather than isolating compiler code generation.

Medians of five operation timings after one warmup, within one process per tier.
The BLAS rows predate folding the bias into the product, and every row predates the
later array and compiler work; see the paired measurements
[with the folded bias](#paired-measurement-folded-bias-and-a-cpython--numpy-baseline) and
[after the array and BLAS work](#paired-measurement-after-the-array-and-blas-work) below.

| Runtime | Full logits + loss | Last-position logits |
|---|---:|---:|
| Upstream PyTorch | 0.658 ms | 0.680 ms |
| Pystachy AOT + OpenBLAS | 0.968 ms | 0.865 ms |
| Pystachy JIT + OpenBLAS | 1.131 ms | 1.087 ms |
| Pystachy scalar AOT | 3.967 ms | 3.776 ms |
| Pystachy scalar JIT | 17.677 ms | 16.535 ms |
| Typed port on CPython | 160.886 ms | 156.050 ms |

For full inference, native BLAS AOT is about 4.1 times faster than scalar AOT
and 166 times faster than the CPython port, while taking 1.47 times PyTorch's
latency. Last-position latency is 1.27 times PyTorch's. Loading, compilation,
output serialization and verification are excluded from these operation timers
and recorded separately. AOT compilation took 1.99 s scalar and 2.12 s BLAS on
this host with the runtime cache available. These are advisory measurements on
shared hardware, with no independent-process confidence interval.

The second training update took 3.176 ms for forward/backward and 0.841 ms for
AdamW with BLAS AOT, versus PyTorch's 2.541 ms and 1.203 ms respectively. This is
one later-step observation; the two-step run is primarily a correctness check.
Across all four model cases and five port execution tiers, 5,309,520 numerical
comparisons passed, with maximum absolute error `1.366e-14`. Comparisons include
full/last logits, losses, all gradients, two parameter updates and both Adam
moments. Tests also cover all-ignored loss/zero gradients. The report retains
the measured controller hash and the published controller hash: subsequent
changes only tightened reused-fixture validation and environment reporting;
the measured model, backward and BLAS sources are identical.

## Paired measurement: folded bias and a CPython + NumPy baseline

This measures folding each block's bias into its BLAS product, against the
separate bias pass of the recorded result, together with a CPython + NumPy port
of the same forward pass ([`nanogpt_numpy_baseline.py`](../../tools/nanogpt_numpy_baseline.py)).
It ran on another host, a shared 4-vCPU Intel Xeon @ 2.80 GHz VM, with the same
benchmark model and fixture, LLVM 18.1.3, CPython 3.12.3, NumPy 2.5.4 with SciPy
1.18.1 (for GELU's exact erf) and PyTorch 2.14.1+cpu on one thread. The native
BLAS rows load SciPy 1.18.1's LP64 OpenBLAS 0.3.31; NumPy uses its own OpenBLAS
build. Compare rows within this table, not with the recorded one.

Each tier ran in seven interleaved rounds, pinned to one CPU; each run timed 200
operations after 20 warmups, and the table gives the median of the runs' medians.
The folded and separate runners alternated their order each round.
[Recorded data](results/folded-bias-paired.json) holds every round's medians.

| Runtime | Full logits + loss | Last-position logits |
|---|---:|---:|
| Upstream PyTorch | 1.141 ms | 1.022 ms |
| CPython + NumPy | 1.324 ms | 1.253 ms |
| Pystachy AOT + OpenBLAS, bias folded | 1.761 ms | 1.691 ms |
| Pystachy AOT + OpenBLAS, separate bias pass | 2.154 ms | 1.969 ms |
| Pystachy JIT + OpenBLAS, bias folded | 2.109 ms | 1.974 ms |

Folding the bias lowered full-inference latency in all seven paired rounds
(median ratio 0.85) and last-position latency in five of seven (0.82); the logits
were bit-identical with and without it. BLAS AOT now takes 1.54 times PyTorch's
and 1.33 times NumPy's full-inference latency, from 1.89 and 1.63 times. NumPy
matched every PyTorch logit and the loss within 3.9e-16. In a profile of the
separate-bias runner, `cblas_dgemm` executed about a fifth of the forward pass's
instructions. Most of the rest was elementwise array work (broadcast adds, layer
norm, GELU's erf, indexing in attention and the loss), output allocation and
collection: the next costs to remove.

```sh
python3 tools/check_nanogpt.py --upstream-model /path/to/nanoGPT/model.py \
  --torch-python /path/to/python-with-torch --benchmark --export-only build/nanogpt-fixtures
/path/to/python-with-torch tools/nanogpt_numpy_baseline.py --fixtures build/nanogpt-fixtures \
  --upstream-model /path/to/nanoGPT/model.py --json build/nanogpt-numpy.json
```

## Paired measurement after the array and BLAS work

This compares inference before and after the changes that followed the measurements above:
- each block's bias folded into its product (#647);
- list repetition (#657) and a collection budget for large arrays (#658);
- in the compiler, index keys made in the caller's frame and cold raise helpers (#681, #684, #695);
- ndarray indexing, elementwise loops and matrix products (#687, #698, #691), and the model's
  direct reads (#688);
- BLAS views lent from an offset instead of copied, with `ffi.at` (#693, #699).

"Before" is main as #642 merged it, with #657, which had merged first, reverted. "After" is main
at [`d97a60c`](https://github.com/den-run-ai/pystachy/commit/d97a60c4aceb43f6e510a0673167b1a0386b3f58), once #699 merged. Both ran on a shared 4-vCPU Intel Xeon @ 2.10 GHz VM with
LLVM 18.1.3, and their BLAS rows load SciPy 1.18.1's LP64 OpenBLAS on one thread. CPython 3.12.3
with NumPy 2.5.4 and PyTorch 2.14.1+cpu ran single-threaded through `nanogpt_numpy_baseline.py`,
and the typed port on CPython 3.13.16. Compare rows within this table, not with the ones above.

Each of ten rounds ran every tier once, pinned to one CPU, in an order rotated by one tier per
round. A run timed 300 operations after 20 warmups (the CPython port 5 after 1), and the table
gives the median over rounds of each run's median.
[Recorded data](results/ndarray-work-paired.json) holds every round's medians, instruction
counts and source hashes.

| Runtime | Full logits + loss | Last-position logits |
|---|---:|---:|
| Upstream PyTorch | 0.710 ms | 0.651 ms |
| CPython + NumPy | 1.139 ms | 0.765 ms |
| Pystachy AOT + OpenBLAS | **0.564 ms** | **0.537 ms** |
| Pystachy AOT + OpenBLAS, before | 1.227 ms | 1.158 ms |
| Pystachy JIT + OpenBLAS | 0.730 ms | 0.881 ms |
| Pystachy JIT + OpenBLAS, before | 1.676 ms | 1.616 ms |
| Pystachy scalar AOT | 2.492 ms | 2.442 ms |
| Pystachy scalar AOT, before | 5.200 ms | 5.091 ms |
| Pystachy scalar JIT | 4.288 ms | 3.191 ms |
| Pystachy scalar JIT, before | 15.852 ms | 16.928 ms |
| Typed port on CPython | 110.9 ms | 152.2 ms |

- **Every tier at least halved its time.** Paired by round, after over before: BLAS AOT 0.46
  (full) and 0.47 (last), BLAS JIT 0.51 and 0.55, scalar AOT 0.47 and 0.49, scalar JIT 0.25 and
  0.19. The scalar JIT gained most: matrix products now step through rows and columns (#691)
  instead of calling the runtime's list helpers for each item, which the JIT cannot inline.
- **Against Python:** BLAS AOT took 0.52 times NumPy's full-inference latency and 0.80 times
  PyTorch's (0.71 and 0.89 for the last position), from 1.24 and 2.10 times before. It ran about
  200 times faster than the typed port on CPython, the noisiest row (101 to 172 ms for full
  inference across rounds).
- **Instructions** (callgrind, one full and one last-position inference): 26.1M before and
  15.2M after with BLAS, 130.7M and 61.6M without.
- **Outputs:** the scalar logits and loss are byte-identical before and after. With BLAS, #699
  lends K's transposed per-head views to OpenBLAS, which sums them in another order: 1,421 of
  2,176 logits differ in the last bit, by at most 3.3e-16, and the loss is identical. Both builds
  match PyTorch within 4.5e-16.
- **Scope:** a small float64 model on one thread, where PyTorch's per-operation overhead
  dominates; in float32 or with more threads PyTorch would gain. The VM is shared: a tier's
  slowest round took 1.2 to 1.9 times its fastest (NumPy's once 3.7 times), so the paired ratios
  are firmer than single rows.

## Reusing autodiff components

The existing microGPT port already uses the scalar reverse-mode engine that
[micrograd recommends as its successor](https://github.com/karpathy/micrograd#training-a-gpt).
Its local derivatives and reverse graph traversal are useful for scalar examples.
Expanding matrix products into individual scalar graph nodes would discard the
main benefit of the ndarray/BLAS path.

[HIPS Autograd](https://github.com/HIPS/autograd) is a useful source of tensor
gradient rules, especially broadcasting reductions, reshapes, transposes and
matrix products. Its current package wraps NumPy dynamically and is not a drop-in
native dependency. A future typed tensor tape could record whole ndarray
operations and reuse this example's validated backward kernels, keeping matrix
products in BLAS. The present example uses explicit analytic backward and does
not provide general automatic or higher-order differentiation. No Autograd or
micrograd code is vendored here; any future source adaptation must retain the
upstream MIT notices.

This example does not implement GPU execution, mixed precision, distributed
training, dropout, the upstream data pipeline or direct `.pt` checkpoint
loading. It demonstrates native execution and supplies bounded correctness and
performance checks; it is not a replacement for the complete upstream project.

Upstream-derived architecture and references are MIT licensed; see [LICENSE](LICENSE)
and the repository's third-party notices.
