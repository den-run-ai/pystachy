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

<a id="paired-measurement-after-the-array-and-blas-work"></a>

## Recorded inference performance

v0.1.0-alpha.4 (`9c8bc746`) runs a small model with 108,288 unique parameters: two layers, two
heads, width 64, context capacity 64, vocabulary 64, bias enabled, batch 2 and sequence length 16.
All paths use float64 and dropout zero; this is not a pretrained GPT-2 throughput result.

Measured on 3 November 2026 on a shared 4-vCPU Intel Xeon @ 2.10 GHz VM, with LLVM 18.1.3 and
one CPU. Native BLAS uses SciPy 1.18.1's LP64 OpenBLAS on one thread. The reference tiers use
CPython 3.13.18 with NumPy 2.5.4 and PyTorch 2.15.0+cpu, single-threaded through
`nanogpt_numpy_baseline.py`; the typed port also runs on CPython 3.13.18.

Each of ten rounds ran every tier once, pinned to one CPU, in an order rotated by one tier per
round. A run timed 300 operations after 20 warmups (the CPython port 5 after 1), and the table
gives the median over rounds of each run's median.
[Recorded data](results/alpha4-paired-2026-11-03.json) holds every round's medians, the
correctness check below and source hashes.

| Runtime | Full logits + loss | Last-position logits |
|---|---:|---:|
| Upstream PyTorch | 0.470 ms | 0.466 ms |
| CPython + NumPy | 0.728 ms | 0.663 ms |
| Pystachy AOT + OpenBLAS | 0.516 ms | 0.477 ms |
| Pystachy JIT + OpenBLAS | 0.640 ms | 0.603 ms |
| Pystachy scalar AOT | 2.113 ms | 2.007 ms |
| Pystachy scalar JIT | 2.697 ms | 2.612 ms |
| Typed port on CPython | 90.26 ms | 85.78 ms |

- **Against Python:** paired by round, BLAS AOT took 0.71 times NumPy's full-inference latency
  and 1.09 times PyTorch's (0.72 and 1.03 for the last position). It ran about 170 times faster
  than the typed port on CPython (180 times for the last position).
- **Outputs:** every run matched the PyTorch reference within 3.9e-16, and each tier's outputs
  were the same in all ten rounds. The BLAS builds' JIT and AOT outputs agree bit for bit, as do
  the scalar builds' and the typed port's.
- **Correctness:** `tools/check_nanogpt.py` also checked every tier against upstream PyTorch on
  four model shapes, including two training steps' gradients and parameters (980,867 values for
  this model), within 1.8e-14.
- **Scope:** these results describe a small float64 model on one thread. Other dtypes and thread
  counts need separate measurement. The VM is shared: a tier's slowest round took up to 1.2 times
  its fastest, so the paired ratios are firmer than single rows.

The measurements before alpha.4, on several builds and hosts, are on
[this page as of alpha.4](https://github.com/den-run-ai/pystachy/blob/9c8bc74648aa7c7e6a1b9d8f9dbbfeb1f2908ad3/examples/nanogpt/README.md#recorded-inference-performance):
the paired comparison of the array and BLAS work at `d97a60c`, an earlier CPU result and a
folded-bias experiment. Their data stay in [`results/`](results/). Their reference rows used
CPython 3.12.3 and PyTorch 2.14.1, so they are not comparable with this table. To time the
reference tiers:

```sh
python3 tools/check_nanogpt.py --upstream-model /path/to/nanoGPT/model.py \
  --torch-python /path/to/python-with-torch --benchmark --warmups 20 --repeats 300 \
  --training-steps 0 --export-only build/nanogpt-fixtures
/path/to/python-with-torch tools/nanogpt_numpy_baseline.py --fixtures build/nanogpt-fixtures \
  --upstream-model /path/to/nanoGPT/model.py --json build/nanogpt-numpy.json
```

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
