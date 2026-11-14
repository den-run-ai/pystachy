# Alpha.2 exact-main performance evidence

[Fresh Performance run](https://github.com/den-run-ai/pystachy/actions/runs/43624131736) compares `a73c56c92f3aad4b490307a5d1b882e487a57f55` with `80490143498d149d407343ba1cb7aedb1db2d2c5`.

The complete artifact contains 11 workloads and 49 paired comparisons. Independent recomputation gives `{"ok": 49}`. Every workload source hash and the runner hash match the qualified tree.

The bootstrap pair took 155.481 s for base and 162.397 s for head (+4.4%). This is one sequential observation per revision.

Host: AMD EPYC 7763 64-Core Processor; Linux-7.0.0-1017-azure-x86_64-with-glibc2.39; Python 3.13.16; CPU affinity [0].

## Paired metric medians

| Workload | Metric | Base seconds | Head seconds | Change | Result |
|---|---|---:|---:|---:|---|
| autograd | build_s | 1.146139 | 0.370681 | -67.66% | ok |
| autograd | jit_process_s | 0.124905 | 0.125683 | +0.62% | ok |
| autograd | jit_loop_s | 0.032947 | 0.033089 | +0.43% | ok |
| autograd | aot_process_s | 0.036834 | 0.036563 | -0.74% | ok |
| autograd | aot_loop_s | 0.031628 | 0.031176 | -1.43% | ok |
| numeric | jit_process_s | 0.157166 | 0.156888 | -0.18% | ok |
| numeric | jit_loop_s | 0.064931 | 0.065033 | +0.16% | ok |
| numeric | aot_process_s | 0.047751 | 0.045093 | -5.57% | ok |
| numeric | aot_loop_s | 0.042539 | 0.039795 | -6.45% | ok |
| fnmatch | build_s | 10.071704 | 7.703809 | -23.51% | ok |
| fnmatch | jit_process_s | 2.435802 | 2.420880 | -0.61% | ok |
| fnmatch | jit_loop_s | 0.036392 | 0.036474 | +0.23% | ok |
| fnmatch | aot_process_s | 0.035773 | 0.036522 | +2.09% | ok |
| fnmatch | aot_loop_s | 0.029910 | 0.030679 | +2.57% | ok |
| json | jit_process_s | 2.422708 | 2.404905 | -0.73% | ok |
| json | jit_loop_s | 0.039339 | 0.039462 | +0.31% | ok |
| json | aot_process_s | 0.040926 | 0.040652 | -0.67% | ok |
| json | aot_loop_s | 0.035170 | 0.034705 | -1.32% | ok |
| repair_scan | jit_process_s | 2.448947 | 2.441423 | -0.31% | ok |
| repair_scan | jit_loop_s | 0.078086 | 0.077358 | -0.93% | ok |
| repair_scan | aot_process_s | 0.076189 | 0.075673 | -0.68% | ok |
| repair_scan | aot_loop_s | 0.070378 | 0.069148 | -1.75% | ok |
| copy_int | build_s | 1.127530 | 0.199098 | -82.34% | ok |
| copy_int | jit_process_s | 0.098545 | 0.100470 | +1.95% | ok |
| copy_int | jit_loop_s | 0.033672 | 0.033653 | -0.05% | ok |
| copy_int | aot_process_s | 0.038051 | 0.038234 | +0.48% | ok |
| copy_int | aot_loop_s | 0.035701 | 0.035766 | +0.18% | ok |
| copy_float | jit_process_s | 0.111710 | 0.112067 | +0.32% | ok |
| copy_float | jit_loop_s | 0.045631 | 0.045545 | -0.19% | ok |
| copy_float | aot_process_s | 0.033643 | 0.035224 | +4.70% | ok |
| copy_float | aot_loop_s | 0.031261 | 0.032652 | +4.45% | ok |
| global_int | jit_process_s | 0.111605 | 0.111225 | -0.34% | ok |
| global_int | jit_loop_s | 0.045600 | 0.045546 | -0.12% | ok |
| global_int | aot_process_s | 0.038027 | 0.038264 | +0.62% | ok |
| global_int | aot_loop_s | 0.035667 | 0.035810 | +0.40% | ok |
| global_float | jit_process_s | 0.110030 | 0.109346 | -0.62% | ok |
| global_float | jit_loop_s | 0.044267 | 0.044161 | -0.24% | ok |
| global_float | aot_process_s | 0.035016 | 0.036285 | +3.62% | ok |
| global_float | aot_loop_s | 0.032715 | 0.033853 | +3.48% | ok |
| graph_copy | build_s | 2.258826 | 0.712010 | -68.48% | ok |
| graph_copy | jit_process_s | 0.233410 | 0.236210 | +1.20% | ok |
| graph_copy | jit_loop_s | 0.067733 | 0.070929 | +4.72% | ok |
| graph_copy | aot_process_s | 0.081572 | 0.082022 | +0.55% | ok |
| graph_copy | aot_loop_s | 0.062971 | 0.063505 | +0.85% | ok |
| regex_effbot | build_s | 6.366316 | 4.560508 | -28.37% | ok |
| regex_effbot | jit_process_s | 1.783835 | 1.769259 | -0.82% | ok |
| regex_effbot | jit_loop_s | 0.308603 | 0.306489 | -0.69% | ok |
| regex_effbot | aot_process_s | 0.264400 | 0.255238 | -3.47% | ok |
| regex_effbot | aot_loop_s | 0.256554 | 0.247495 | -3.53% | ok |

## Interpretation limits

- Eleven bounded workloads on one shared CI host and one pinned CPU; not a whole-project performance claim.
- Three interleaved base/head samples per metric, with three more only when the first median slowdown is at least 20% and 5 ms. Confirmed warnings also require nonoverlapping ranges in both batches.
- Builds use warmed runtime caches; the program cache is disabled. JIT process times include frontend and LLVM work; AOT process times include process startup.
- graph_copy loop time is CPU time; other loop times are wall time. The medians describe this run and do not establish sustained changes by themselves.
- This artifact does not measure executable size or peak RSS. Earlier paired local executable-size measurements remain separate evidence.

Source report SHA-256: `fb048bd33de058f38336aef962fb57674acf0f9b5053248d832e98d138c16f1c`.
