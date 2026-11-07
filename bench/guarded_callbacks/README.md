# Compiler-generated callback specialization

This experiment compiles the same ordinary Python scoring program twice. The
`generic` measurement sets `PYSTACHY_OPT=-callbacks`; `guarded` uses the default
compiler options. Both execute [`workload.py`](workload.py), which imports the
single [`score` function](../../examples/guarded_score/scoring.py). There are no
application-authored guards or separate implementations in the input program.

## Reproduce

Run from the repository root on Linux with the pinned CPython and LLVM installed:

```sh
python3 bench/guarded_callbacks/bench.py --smoke --jit all \
  --json build/guarded-callbacks-smoke.json
python3 bench/guarded_callbacks/bench.py --samples 7 --jit all \
  --keep build/guarded-callbacks-artifacts \
  --json build/guarded-callbacks.json
```

Use the interpreter named in `.python-version` (or substitute its executable path
for `python3`). `--compiler` selects one native compiler binary; `--cpu` selects an
allowed CPU, defaulting to the lowest available CPU. `--keep` must name a new
directory. `--smoke` uses tiny inputs and reports correctness only.

The controller pins one CPU, alternates measurement order, checks every result
against CPython, and records source hashes, tool versions, raw timings, IR,
binary sizes and GC probes. Each compiler option uses its own runtime cache and
is applied to IR generation, AOT compilation and **every JIT invocation**. Seven
paired process samples and three paired builds are the defaults. Schema version 2
records one shared program and the options for each variant.

## Scope and interpretation

The eight controls cover squared error, absolute error, a 99/1 known-target/closure
mix, alternating known targets, all closure calls, a mid-run switch to closures,
one-value batches and fresh input construction. Inputs and schedules are built
before the timed region, except that the fresh-input case rebuilds both lists in
every measured batch. The timed kernel includes callback selection from the
schedule and the full score call, including validation. JIT process time includes
compilation and startup; its kernel timing does not.

These measurements target repeated callbacks over typed lists. They do not
establish a 2x improvement for an existing application, heterogeneous storage or
construction-heavy processing. The compiler transformation uses a bounded set of
precompiled variants; it does not learn a runtime profile or compile new code on
a miss. Fallback behavior must preserve captured environments, callback effects,
exceptions, mutation order and floating-point accumulation order.

**Measurements for the compiler implementation are pending.** Do not use the
historical manual-guard results as performance evidence for the new compiler pass.

## Historical experiment

The original manually guarded prototype demonstrated the opportunity before the
compiler transformation existed. Its source, explanation and measurements are
preserved at [commit `16d90a5`](https://github.com/den-run-ai/pystachy/blob/16d90a566000b6aaedd372824d8f47d158ccb744/examples/guarded_score/README.md).
Its approximately 4x AOT result applies only to that historical source and setup.

The original JSON artifacts have moved unchanged into
[`results/manual-guards-2026-11-06`](results/manual-guards-2026-11-06/). Their source
paths and validation records describe the old commit, including its two manually
written APIs. They are retained for provenance; current measurements belong in
separate files alongside them.
