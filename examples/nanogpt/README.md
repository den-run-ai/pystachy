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

This example does not implement GPU execution, mixed precision, distributed
training, dropout, the upstream data pipeline or direct `.pt` checkpoint
loading. It demonstrates native execution and supplies bounded correctness and
performance checks; it is not a replacement for the complete upstream project.

Upstream-derived architecture and references are MIT licensed; see [LICENSE](LICENSE)
and the repository's third-party notices.
