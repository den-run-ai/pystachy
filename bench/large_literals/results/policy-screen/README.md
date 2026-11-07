# Scalar literal inline-policy screen

Source: main `f7103067545b43cdcd8ce20dc66b1571425b3a8d` versus branch `1cd9a9d1` (production changes through `f969e355`). This is a **policy screen**, before final production revision `6ad66566` removes `noinline`. Current source is emitted under CPython 3.13.16; no old native compiler binary supplies the frontend. LLVM is 18.1.3 on x86-64 Linux, affinity CPU 3. `PYTHONHASHSEED=0` was set for the invocation.

Each input has one frozen backend replay per policy and five interleaved fresh-process execution samples. The exact source/tool/linked-input hashes, commands, stage wall/CPU/RSS values, output hashes and observed host load are in [results.json](results.json). All 18 build witnesses and 90 timed execution witnesses matched CPython stdout, empty stderr and exit 0. Source stayed unchanged, and the candidate policy variants began from byte-identical raw IR and linked bitcode.

`candidate` retains the original forced `noinline`; `candidate-inline` removes only that attribute before program O2. It reuses the exact candidate runtime, and its attribute-edit setup time is separately recorded and excluded from backend totals. Runtime preparation is also excluded. This split optimizer/codegen replay is neither ordinary driver latency nor compiler-bootstrap latency.

## Decision

Leave the helper eligible for normal LLVM inlining. Forced `noinline` is unnecessary for the observed code-size bound: with normal eligibility, optimized instruction-line counts stay exactly flat from 32 to 4,096 items (6,298 for escaping lists, 6,161 for local lists). Normal eligibility leaves the local length constant visible and removes its dynamic bounds test. It adds about 192 bytes of object text in this screen, with a further 16-byte difference for the 4,096-item local case.

Both policies are faster than the old append sequence on these eligible workloads. The ranking between the two new policies is mixed and noisy: normal eligibility has a lower local-32 median but a higher escaping-32 median, with overlapping ranges. This does not establish a generally fastest inlining policy. It supports using LLVM’s ordinary eligibility rather than forcing a boundary without evidence that it is required. Optimized-code-size guarantees remain target/pipeline dependent; the frontend instruction bound is deterministic.

## Backend observations (one build per cell)

| Input | Baseline seconds | Forced noinline seconds | Normal eligibility seconds |
|---|---:|---:|---:|
| int-escape-31 | 0.507705 | 0.555012 | 0.561895 |
| int-escape-32 | 0.593508 | 0.498970 | 0.544854 |
| int-escape-4096 | 0.744089 | 0.523926 | 0.560249 |
| int-local-31 | 0.564783 | 0.552356 | 0.546205 |
| int-local-32 | 0.564297 | 0.521475 | 0.524472 |
| int-local-4096 | 0.928582 | 0.562385 | 0.576670 |

## Execution (median and observed range, milliseconds)

These are complete fresh-process times, including printing one full list. The 31/32-item inputs perform 645,162/625,000 constructions; 4,096-item inputs perform 5,000. No startup time is subtracted. The final narrow repeated study uses more constructions to reduce the short-case timing floor.

| Input | Baseline median [range] | Forced noinline median [range] | Normal eligibility median [range] |
|---|---:|---:|---:|
| int-escape-31 | 96.443 [84.994–108.492] | 90.389 [83.655–111.471] | 96.504 [84.784–103.691] |
| int-escape-32 | 90.080 [85.133–108.530] | 39.791 [36.736–47.446] | 47.022 [42.149–50.192] |
| int-escape-4096 | 79.512 [76.883–99.949] | 9.416 [9.037–11.845] | 10.065 [8.848–11.572] |
| int-local-31 | 70.784 [69.539–78.932] | 69.716 [68.100–72.449] | 69.848 [69.211–71.518] |
| int-local-32 | 79.661 [68.256–95.221] | 32.168 [30.919–45.955] | 27.884 [25.256–44.599] |
| int-local-4096 | 77.081 [74.089–82.877] | 9.009 [8.124–10.120] | 8.392 [8.147–8.666] |

## Structural and memory observations

Each cell is baseline → normal eligibility. Instruction figures count LLVM instruction-shaped lines in the complete module, including needed runtime code. Object text is the sum of `.text*` sections; immutable data is separately accounted for in the raw JSON. RSS is the largest per-command `wait4` maximum among replay phases, not aggregate simultaneous RSS.

| Input | Raw IR instruction lines | Optimized instruction lines | Object text bytes | Executable bytes | Max phase RSS MiB |
|---|---:|---:|---:|---:|---:|
| int-escape-31 | 140 → 140 | 6302 → 6302 | 30,323 → 30,323 | 69,016 → 69,016 | 97.13 → 97.83 |
| int-escape-32 | 141 → 109 | 6303 → 6298 | 30,339 → 30,083 | 69,016 → 68,976 | 97.41 → 97.19 |
| int-escape-4096 | 4205 → 109 | 10367 → 6298 | 87,235 → 30,083 | 126,360 → 101,744 | 114.76 → 98.13 |
| int-local-31 | 161 → 161 | 6215 → 6215 | 30,195 → 30,195 | 68,872 → 68,872 | 97.76 → 97.80 |
| int-local-32 | 163 → 99 | 6217 → 6161 | 30,227 → 29,443 | 68,872 → 68,872 | 97.80 → 98.02 |
| int-local-4096 | 8291 → 99 | 14349 → 6161 | 144,067 → 29,459 | 183,632 → 101,640 | 118.68 → 98.09 |

The 31-item negative controls produced byte-identical executables across all three policies. Their timing differences therefore demonstrate measurement variation rather than a code change.

Inspection of optimized loop bodies confirms that both escaping and local controls still construct lists per iteration. In the local-32 case, normal eligibility leaves allocation plus a 256-byte `llvm.memcpy` inside the loop backedge; it does not optimize the whole loop into a constant. The forced helper leaves a call inside the loop instead. Function excerpts and the original module hashes are preserved under `witnesses/`; they are excerpts, not standalone LLVM modules.

No tuple-item, pointer-bearing, dynamic-Any or promoting-int performance improvement is claimed. The initial direct-source inventory found three compiler tables (40/64 lexer ranges and 68 decimal-run starts). The later full corpus also exercises scalar transition tables generated by regex specialization; those were absent from that direct-source inventory. This is not evidence of a material whole compiler self-build speedup. Final native source validation and narrow repeated baseline/candidate timing follow the policy choice.
