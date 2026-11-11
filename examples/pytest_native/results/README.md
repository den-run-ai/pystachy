# Illustrative native-runner measurements

[Raw samples and source hashes](2026-11-10.json) measure the five cases in
`test_compute.py`: integer arithmetic and repeated text wrapping. This small suite
is not a general pytest benchmark or a measurement of CPython interpreter tests.

On Linux x86-64, with CPython 3.13.16, pytest 9.2.0 and LLVM 18.1.3, five
interleaved runs gave these process-execution medians:

| Execution | Median | What executes |
|---|---:|---|
| Original source with pytest | 234.8 ms | CPython, including collection and assertion rewriting |
| Generated runner with CPython | 53.7 ms | CPython, with collection and fixture calls generated ahead of time |
| Generated AOT executable | 18.4 ms | Pystachy's native code and supported library implementations |

All 15 timed executions matched the five collected case IDs and their setup,
call and teardown outcomes. Each timing includes a fresh process and outcome-file
writes; compilation and validation parsing are excluded. Runs used one allowed
CPU with rotating order. The raw record includes host load, settings, commands,
versions, per-sample times and hashes of compiler/runtime/library and generated
sources. Arithmetic loops may optimize heavily; text wrapping is included to
exercise a real library workload.

The generated CPython runner was **4.4× faster** than pytest for this suite while
still executing test bodies and library operations under CPython. Native execution
was **2.9× faster** than that generated CPython run, or **12.8×** compared with
pytest. These ratios describe this suite's complete process runs, not all pytest
features or general application speedups.

The initial AOT build took **17.1 seconds** with a fresh private runtime cache.
Using that cost and the measured medians, roughly **79 unchanged runs** would
amortize compilation against pytest, or **484** against the generated CPython
runner. These are estimates excluding collection/controller overhead and changes
that require rebuilding; a single execution was much slower when compilation is
included.

To reproduce with an installed matching LLVM toolchain and a Python environment
containing pytest 9.2.0:

```sh
PYSTACHY_LLVM=/path/to/llvm/bin python examples/pytest_native/benchmark.py \
  --samples 5 --work-dir /tmp/pystachy-pytest-benchmark \
  --json /tmp/pystachy-pytest-benchmark.json
```

Use a fresh work directory for an initial-build measurement. The benchmark fails
on collection/outcome differences and reports build costs separately; it does not
enforce a noisy timing threshold.
