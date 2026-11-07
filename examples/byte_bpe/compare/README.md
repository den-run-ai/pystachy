# Byte-BPE runtime comparison

`run.py` builds and checks the educational byte-BPE implementation, then compares
separate training, encoding and decoding stages. It reuses the original showcase's
process/RSS observer and pinned upstream extraction. The numerical work in
`stages.py` is identical to the driver used for the
[recorded comparison](../results/runtime-comparison-2026-11-07/README.md).
The portable controller was prepared after those measurements; its smoke runs are
correctness checks, not replacements for the recorded performance samples.
Source adapters retain Shantanu Jain's educational pyperformance/tiktoken code;
see [upstream provenance](../upstream/provenance.json) and the project's
[third-party notices](../../../THIRD_PARTY_NOTICES).

## Requirements

Use a POSIX host with `wait4`. CPU pinning and sampled main-process RSS require
Linux; without `/proc`, sampled RSS is unavailable. Install the desired runtimes
yourself: this controller never installs packages or downloads sources. A native
Pystachy compiler and a matching complete LLVM installation are required for the
Pystachy modes. Follow the repository's [build instructions](../../../docs/install.md).

The recorded comparison used CPython 3.13.16, PyPy 8.0.1/Python 3.11.17,
Cython 3.3.1, mypy/mypyc 2.4.1, setuptools 80.9.0, GCC 13.3.0 and LLVM 18.1.3.
For comparable extension builds, install these build packages into the **same
CPython environment used for the interpreted baseline**:

```sh
python3.13 -m venv /tmp/bpe-comparison-venv
/tmp/bpe-comparison-venv/bin/python -m pip install \
  Cython==3.3.1 mypy==2.4.1 setuptools==80.9.0
```

The script records actual versions, flags, source and artifact hashes, build
commands, build times, source identities and affinity. Different toolchains or
machines produce new evidence rather than automatically reproducing old numbers.
Build artifacts are always fresh. `--work-dir` retains them in a new directory;
an existing directory is rejected. Otherwise the temporary workspace is removed
after the JSON report has been saved. `--runtime-cache` optionally reuses a named
Pystachy runtime cache; generated benchmark binaries are still rebuilt.

## Run

From the repository root, choose an available CPU and absolute runtime/tool paths:

```sh
/tmp/bpe-comparison-venv/bin/python examples/byte_bpe/compare/run.py \
  --python /tmp/bpe-comparison-venv/bin/python \
  --pypy /path/to/pypy3.11 \
  --compiler ./pystachy --llvm /path/to/llvm-18/bin \
  --cpu 0 --processes 5 \
  --work-dir /tmp/bpe-comparison-build \
  --output /tmp/bpe-comparison.json
```

Add `--smoke` for one process per mode on a tiny corpus with vocabulary size 264
and one timed encode/decode iteration. The warmup counts remain unchanged. Smoke
numbers must not be used as performance results. A lightweight check needs only
CPython:

```sh
python3.13 examples/byte_bpe/compare/run.py \
  --modes cpython_original,cpython_adapted --smoke \
  --output /tmp/bpe-comparison-smoke.json
```

The default modes reproduce the primary matrix:

| Mode | Source and compiler adaptation |
|---|---|
| `cpython_original` | Exact pinned upstream class/function text; unused upstream runner omitted |
| `cpython_adapted` | Pystachy's port executed by the same CPython |
| `cython_original` | Entire unchanged upstream source compiled with Cython and `-O3` |
| `cython_scalar` | Upstream plus two `cython.locals` decorators and `import cython`; safety checks retained |
| `cython_adapted` | Pystachy's port compiled with Cython and `-O3` |
| `mypyc_original` | Upstream plus one required `Counter[tuple[bytes, bytes]]` annotation; optimization level 3 |
| `pypy_original` | The same exact upstream kernels as original CPython |
| `pystachy_aot` | Pystachy's port, freshly built AOT |
| `pystachy_scalar_tuple` | A separately labelled AOT diagnostic replacing comparison-tuple creation with scalar bytes comparisons |

The extension launcher rejects a Python-source fallback or an extension from a
different directory. The unused upstream runner imports `pyperf`; a tiny local
stub supplies only `perf_counter`, and a typing stub lets mypyc inspect that
unused runner. All measured work uses the common stage driver. The adapters are
checked against the exact source hashes from the recorded experiment. No Cython
native-container rewrite is included.

Optional secondary modes are `pystachy_jit`, `pystachy_jit_inline100k` and
`pystachy_aot_gc8`. Run them as a separate series, for example:

```sh
python3.13 examples/byte_bpe/compare/run.py \
  --compiler ./pystachy --llvm /path/to/llvm-18/bin --cpu 0 --processes 3 \
  --modes pystachy_jit,pystachy_jit_inline100k,pystachy_aot_gc8 \
  --output /tmp/bpe-secondary.json
```

Include both `pystachy_aot` and `pystachy_aot_gc8` in a new interleaved series to
test GC throughput directly. Comparing medians from different series does not
establish that changing the threshold improved throughput.

## Protocol and interpretation

The full workload uses the pinned 31,206-byte Frankenstein corpus and vocabulary
size 1,024. Each process runs two training warmups, one timed training, 20 encoding
warmups, 50 timed encodes, 100 decoding warmups and 200 timed decodes. First and
second training times are retained separately. This is a fixed warmed protocol;
it does not prove convergence of PyPy's JIT. Processes run serially in a rotating
order, reversed on alternate rounds. Compilation, imports, I/O and validation are
outside the stage timers. Whole-process wall time includes all of them plus the
warmups, so it is not single-query latency.

Before accepting timings, the runner executes the byte-level correctness fixture
under every selected mode, including per-allocation GC stress for the two primary
AOT modes (`pystachy_aot` and `pystachy_scalar_tuple`).
It accepts only the three demonstrated Python-version variants of the exhausted
`max()` error text. It then compares every sample's complete ordered vocabulary,
token IDs, decoded bytes and decoded text with a freshly generated original
CPython oracle. Malformed, missing, duplicate, zero or nonfinite timing rows fail
the run. Inputs/artifacts are rehashed afterwards. A failure replaces the output
report's success status with `failed`.

Sampled RSS is main-process `VmHWM` after the requested command has been installed,
observed approximately every 5 ms. It includes warmups and the interpreter or
JIT compiler process, excludes compiler child processes, and may miss very short
processes. The retained `wait4` RSS has different semantics, including a possible
pre-exec launcher high-water mark. Do not mix the two memory metrics.

Run the controller contract tests in the existing Lint job's form:

```sh
python3.13 -m unittest discover -s tools -p test_byte_bpe_comparison.py
```

The main stage comparison does not reproduce the separately archived encoding
decomposition or longer-warmup experiment. Their call sites, warmup counts and
native inlining differ; keep those diagnostics separate from the primary matrix.
