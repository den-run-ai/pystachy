# Native compiler stage cost probe

This measures native **source-to-LLVM self-compilation** of the same current
`pystachy.py` and dependency tree. It excludes LLVM optimization, machine-code
generation, linking and execution of the resulting compiler. No speedup or
precise overhead is established by these five noisy pairs.

## Method and identity

The reference compiler is main `80490143`; the staged compiler corresponds to
PR head `800752d8a582bff77d4c375039af786b82a96f73`. Both compile the current
source tree using the same `PYSTACHY_HOME`, library and runtime inputs. All other
`PYSTACHY_*` settings are cleared, then `PYSTACHY_GC=stats` and
`PYSTACHY_TIMING=1` are enabled. Children run serially on allowed CPU 0, after the
task's other local builds/tests finished. The host remains shared.

One warmup per compiler is excluded. Five pairs alternate main/stages then
stages/main. Wall time includes process startup and output writing; `wait4`
records each child's CPU time and peak RSS. The raw report retains per-stage
timings, GC summaries, load observations, commands, input hashes and binary
hashes. Nested stage timings must not be added together.

The local branch moved from `c153493a7c5a11196fd42a8591bcf7e062f5ac34` to the
published head during sampling. Both have tree
`f85536e8286db9a585fdb4d6606e8b8af8f67eb8`; source bytes and compiler hashes were
independently unchanged before/after the run. This equivalence and paired ratios
were added to the report after sampling.

## Results

| Metric | Main | Staged |
|---|---:|---:|
| Median wall time | 10.786 s | 10.053 s |
| Wall-time range | 8.912–11.354 s | 9.089–11.372 s |
| Median total CPU time | 10.683 s | 9.932 s |
| Median peak RSS | 943,532 KiB | 938,744 KiB |
| GC heap peak, every run | 917.4 MiB | 912.8 MiB |
| GC collections, every run | 14 | 14 |
| Median GC time | 1,412.9 ms | 1,465.8 ms |
| Live heap at the last GC, every run | 191.0 MiB | 191.5 MiB |
| Compiler executable size | 6,712,704 bytes | 6,724,320 bytes |

The executable grew by 11,616 bytes (0.173%). Separate wall-time medians favor
the staged compiler, while the median within-pair staged/main ratio is 1.052
(range 0.801–1.055). This disagreement and the overlapping ranges prevent a
defensible speed claim. Heap statistics describe this workload and collector
observation; they are not general memory or lifetime guarantees.

All twelve outputs, including warmups, are exactly 35,162,543 bytes with SHA-256
`24f6bd34684388320538699315afcf2095eeaf633196eeca194fe473471e1ba8`.
The large identical LLVM files are omitted here; every sample's hash and size
remain in [report.json](report.json). Raw stdout/stderr logs are retained.
`PYSTACHY_GC=stats` reports collections and heap measurements, **not allocation
counts**. Allocation requests were not measured; that requires a separately
instrumented runtime built with `PYSTACHY_PROFILE_DATA`.

## Reproduce

On the staged checkout, with the pinned development Python and matching LLVM
toolchain configured, first build both native compilers:

```sh
make PY=python3.13
make ref REF=80490143 PY=python3.13
python3.13 /path/to/measure_stage_overhead.py --root "$PWD"
```

Use the retained [runner](measure_stage_overhead.py). Run it after other local
heavy work finishes. It selects the lowest allowed CPU (or accepts `--cpu N`),
creates a fresh output directory, preserves every LLVM output and log, requires
identical output hashes and rejects source/binary changes during measurement.
