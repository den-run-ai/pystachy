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
`libblas.so.3` backend. That library must provide the documented LP64 ABI.

For CPython comparison, set `PYTHONPATH` to the same example directories and run
`python3 examples/nanogpt/run.py ...`. The BLAS CPython twin additionally needs
`tools/rt_cpython` on that path; it copies lists and does not model native FFI cost.

## API and file format

`GPTConfig(n_layer, n_head, n_embd, block_size, vocab_size, bias)` and
`GPT(config, parameters)` construct a model. `forward(model, tokens, batch,
length, last_only=False)` uses scalar matrix products; `forward_with_backend`
accepts a compatible `matmul(a, b)` callback. Tokens are flattened in batch-major
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

## Native training

[`training.py`](training.py) supplies analytic backward kernels and AdamW. It
shares the forward implementation and caches activations, and accumulates both
uses of the tied token/output parameter into one gradient. For example:

```python
from driver import read_input
from model import load_weights
from ndarray_blas import matmul
from training import AdamW, loss_and_grad_with_backend

model = load_weights("model.weights")
inputs = read_input("batch.input")
optimizer = AdamW(model)
for step in range(10):
    result = loss_and_grad_with_backend(
        model, inputs.tokens, inputs.targets, inputs.batch, inputs.length, matmul)
    optimizer.step(result.gradients)
    print(step, result.loss)
```

Use `ndarray.matmul` for the scalar backend. Parameters and gradients must be
whole contiguous arrays. AdamW validates every gradient before any parameter
mutation and applies weight decay only to parameters with at least two dimensions,
matching upstream grouping. A new gradient dictionary is returned per call.
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

Medians of five operation timings after one warmup, within one process per tier:

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
