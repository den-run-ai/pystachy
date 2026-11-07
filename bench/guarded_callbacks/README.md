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
schedule and the full score call, including validation. Runtime caches are warmed
before measurement. Complete JIT command timings include program compilation
and startup; kernel timings do not. Reported build costs exclude a cold runtime
build.

These measurements target repeated callbacks over typed lists. They do not
establish a 2x improvement for an existing application, heterogeneous storage or
construction-heavy processing. The compiler transformation uses a bounded set of
precompiled variants; it does not learn a runtime profile or compile new code on
a miss. Fallback behavior must preserve captured environments, callback effects,
exceptions, mutation order and floating-point accumulation order.

## Compiler implementation results

[Source `9e4ae462`](https://github.com/den-run-ai/pystachy/commit/9e4ae4624f4bcd8ac37dcdd73344ac856e43a222),
LLVM 18.1.3, CPython 3.13.16, x86-64 Linux: seven alternating pairs pinned to one
CPU. Every measured result matches CPython. Ratios are paired medians, generic
time divided by guarded time; values above 1 favor specialization.

| Workload | AOT kernel | JIT kernel | Complete JIT command |
|---|---:|---:|---:|
| Squared error | 4.01x | 1.74x | 1.47x |
| Absolute error | 4.06x | 1.73x | 1.37x |
| 99% known, 1% closure | 3.86x | 1.72x | 1.42x |
| Alternating known callbacks | 4.18x | 1.73x | 1.49x |
| All closure fallback | 1.02x | 0.98x | 0.97x |
| Switch to closures halfway | 1.65x | 1.27x | 1.14x |
| One value per batch | 1.16x | 1.08x | 0.93x |
| Construct inputs every batch | 1.16x | 1.11x | 1.01x |

The large known-target AOT gain is consistent across all seven pairs. The
fallback control is approximately at parity; its AOT ratios span 0.76-1.19x.
Short-batch AOT ratios span 0.55-1.31x, so their median is not a reliable small
speedup claim. Compilation and startup can outweigh the kernel gain in short JIT
commands. These are shared-host observations, not performance gates.

The linked executable's text grows from 71,822 to 72,238 bytes (**416 bytes**).
Both executable files are 95,792 bytes. Disassembly retains the generic indirect
call and exposes subtraction/multiplication or absolute-value arithmetic in the
two guarded loops. The squared-error GC probes report the same **2.0 MiB** heap
peak and zero collections; this is not a process-RSS measurement. Three paired
AOT builds show a median **5.2%** build-time increase.

[Raw measurements](results/llvm18-compiler-2026-11-06.json) include all samples,
input/compiler/source hashes, tool identities, build costs and GC probes.
[Code shape](results/code-shape-compiler.json) records the measured executable
sections and scoring-function disassembly.

## Compiler validation

[Validation evidence](results/validation-compiler.json) records the tested source,
compiler binary, commands and scope. Fresh compiler and runtime fixed points pass,
as do `check-fast`, lint, runtime contract checks and focused native differential
cases with the pass enabled, disabled, all optimizations disabled and forced GC.
The 4,243-case IR/diagnostic comparison has five intentional kernel changes and
no new diagnostics or exit-status changes after removing checkout-path noise by
using verified identical library/runtime inputs. Full local `make verify` was
not run; the PR remains draft pending the required CI matrix.

The historical manual-guard data below is separate evidence.

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
