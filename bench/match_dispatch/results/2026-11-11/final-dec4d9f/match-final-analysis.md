# Match performance evidence

If/match ratios above 1 favor match; below 1 favor handwritten conditions.

Controller kernel timers exclude input construction, validation, warm-up, compilation and startup. Pyperf command timings include the complete AOT subprocess. Correctness is established by the controller and the manifest's checksum-checked preflight; pyperf command itself discards child stdout/stderr and checks exit status.

All statistics are descriptive. Pair spans and min–max ranges are observed extrema, not confidence intervals. SD is the sample standard deviation (n−1). CV is SD/mean. The 10% CV flag belongs to this analyzer and is not a statistical significance test.

Pyperf values are seconds per command invocation as stored by pyperf. Warmups and calibration-only runs are excluded. Values within a worker share a process history, so the total value count is not the number of independent workers. Its mean/median comparisons are ratios of separate summaries, not pairwise value ratios.

## Primary completed measurement

Recorded commit: `dec4d9f1c0d91046a9ddfbb55e63ab5a897a40f6`. Measured modes: aot, jit.

### Kernel timings

| Cell | Mode | Match median ms | If median ms | If/match median | Observed pair span | Pairs | CV match / if |
| --- | --- | --- | --- | --- | --- | --- | --- |
| literal-mixed | jit | 62.780 | 71.196 | 1.119 | 1.115–1.479 | 7 | 3.0% / 9.7% |
| literal-mixed | aot | 70.763 | 95.713 | 1.340 | 1.057–1.440 | 7 | 9.9% / 2.8% |
| literal-skewed | jit | 40.697 | 46.039 | 1.109 | 0.852–1.518 | 7 | 11.2% / 11.0% |
| literal-skewed | aot | 41.581 | 79.127 | 1.899 | 1.839–1.992 | 7 | 2.7% / 1.2% |
| tuple-mixed | jit | 138.129 | 64.027 | 0.474 | 0.458–0.498 | 7 | 1.4% / 3.0% |
| tuple-mixed | aot | 76.521 | 82.370 | 1.077 | 1.044–1.103 | 7 | 1.3% / 1.2% |
| tuple-skewed | jit | 95.954 | 60.467 | 0.632 | 0.472–0.745 | 7 | 10.9% / 7.9% |
| tuple-skewed | aot | 50.658 | 53.159 | 1.060 | 0.951–1.470 | 7 | 6.1% / 21.8% |
| dataclass-mixed | jit | 139.153 | 74.650 | 0.536 | 0.449–0.729 | 7 | 7.4% / 12.4% |
| dataclass-mixed | aot | 79.745 | 71.805 | 0.886 | 0.835–0.916 | 7 | 2.9% / 3.4% |
| dataclass-skewed | jit | 118.218 | 60.535 | 0.496 | 0.365–0.528 | 7 | 17.3% / 4.4% |
| dataclass-skewed | aot | 52.390 | 57.935 | 1.106 | 0.960–2.063 | 7 | 2.4% / 30.9% |

### AOT whole-command pyperf

| Cell | Variant | Mean s | Median s | Sample SD s | CV | Values | Workers | Min–max s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| literal-mixed | match | 0.726074 | 0.717003 | 0.034695 | 4.78% | 15 | 3 | 0.699270–0.821447 |
| literal-mixed | if | 0.968122 | 0.967114 | 0.022416 | 2.32% | 15 | 3 | 0.941939–1.025375 |
| literal-skewed | match | 0.462974 | 0.444949 | 0.052572 | 11.36% | 15 | 3 | 0.413245–0.584198 |
| literal-skewed | if | 0.847223 | 0.831939 | 0.063857 | 7.54% | 15 | 3 | 0.788657–1.054049 |
| tuple-mixed | match | 0.803531 | 0.793883 | 0.051202 | 6.37% | 15 | 3 | 0.756880–0.966269 |
| tuple-mixed | if | 0.852888 | 0.844330 | 0.027966 | 3.28% | 15 | 3 | 0.827321–0.933891 |
| tuple-skewed | match | 0.516968 | 0.511947 | 0.016652 | 3.22% | 15 | 3 | 0.499574–0.551073 |
| tuple-skewed | if | 0.604359 | 0.600308 | 0.059887 | 9.91% | 15 | 3 | 0.526177–0.768437 |
| dataclass-mixed | match | 0.804894 | 0.807573 | 0.022778 | 2.83% | 15 | 3 | 0.777556–0.868800 |
| dataclass-mixed | if | 0.731106 | 0.726714 | 0.016737 | 2.29% | 15 | 3 | 0.715037–0.778859 |
| dataclass-skewed | match | 0.607160 | 0.547740 | 0.114080 | 18.79% | 15 | 3 | 0.520345–0.813362 |
| dataclass-skewed | if | 0.596428 | 0.606601 | 0.022322 | 3.74% | 15 | 3 | 0.541982–0.617102 |

| Cell | If/match ratio of means | If/match ratio of medians |
| --- | --- | --- |
| literal-mixed | 1.333 | 1.349 |
| literal-skewed | 1.830 | 1.870 |
| tuple-mixed | 1.061 | 1.064 |
| tuple-skewed | 1.169 | 1.173 |
| dataclass-mixed | 0.908 | 0.900 |
| dataclass-skewed | 0.982 | 1.107 |

### Recorded identities

| Item | Recorded value |
| --- | --- |
| Compiler command | ["/workspace/scratch/0bc6e8bc1edf/match-main/pystachy"] |
| Compiler executable SHA-256 | 39177cf908ec1b681ea133db3d830e5c9c12dff6ddbb7de46189166a913e74dc |
| AOT executable SHA-256 | da6dcda2fa6ed927bed503f5e7ca6e079d15bd474fcf5db57bae65806246bc46 |
| Source manifest SHA-256 | b869aaef104ac16a198351f5c9fb491cb5bb3976a9810baaf5c7a5bbb89409b3 |
| Source files | 161 |
| Workload source SHA-256 | 98bd8300b8221557c1c0a10441d706f1260416ad1732c16344688581fa381e55 |
| CPU / affinity | INTEL(R) XEON(R) PLATINUM 8573C / [0] |
| CPython | 3.13.16 (main, Oct 14 2026, 01:04:01) [Clang 23.1.3 ] |
| pyperf | 2.11.0 |

| Tool | Version | SHA-256 |
| --- | --- | --- |
| clang | Ubuntu clang version 18.1.3 (1ubuntu1) | 8ef402d453d1ba4902e4ee0f0f847f6cfa01400c95aa43c24e97818b9c0e3f45 |
| opt | Ubuntu LLVM version 18.1.3 | 67ebe8635087b5ebe22d8f085d5e5857e431f86be9ed76576e59b86b9743c0fb |
| lli | Ubuntu LLVM version 18.1.3 | f787c770f5281ab909eac3d28ed984d8f0759caf87def4794f432fd008ef4f8c |
| llvm-link | Ubuntu LLVM version 18.1.3 | e340363ed9e5346f0d6dc4441f4953c5f516ff73fa0a03e1955c1adaad68b651 |
| llvm-as | Ubuntu LLVM version 18.1.3 | 8e7460eff4ba4e22d8ae881404bb24c5fc346996264e883ba26d41da4188215d |

Identities are copied from the measurement records; the analyzer does not inspect current compiler/source files. The full source-hash map remains in the controller report, and its canonical hash is recorded above.

### Dispersion and evidence cautions

- kernel literal-mixed/jit/if: maximum exceeds the median by more than 20%; inspect the retained observations.
- kernel literal-mixed/aot/match: maximum exceeds the median by more than 20%; inspect the retained observations.
- kernel literal-skewed/jit/match: CV 11.197% exceeds the analyzer's descriptive 10% flag.
- kernel literal-skewed/jit/match: maximum exceeds the median by more than 20%; inspect the retained observations.
- kernel literal-skewed/jit/if: CV 11.041% exceeds the analyzer's descriptive 10% flag.
- kernel literal-skewed/jit/if: maximum exceeds the median by more than 20%; inspect the retained observations.
- kernel tuple-skewed/jit/match: CV 10.944% exceeds the analyzer's descriptive 10% flag.
- kernel tuple-skewed/jit/match: maximum exceeds the median by more than 20%; inspect the retained observations.
- kernel tuple-skewed/aot/if: CV 21.762% exceeds the analyzer's descriptive 10% flag.
- kernel tuple-skewed/aot/if: maximum exceeds the median by more than 20%; inspect the retained observations.
- kernel dataclass-mixed/jit/if: CV 12.428% exceeds the analyzer's descriptive 10% flag.
- kernel dataclass-mixed/jit/if: maximum exceeds the median by more than 20%; inspect the retained observations.
- kernel dataclass-skewed/jit/match: CV 17.292% exceeds the analyzer's descriptive 10% flag.
- kernel dataclass-skewed/jit/match: maximum exceeds the median by more than 20%; inspect the retained observations.
- kernel dataclass-skewed/aot/if: CV 30.856% exceeds the analyzer's descriptive 10% flag.
- kernel dataclass-skewed/aot/if: maximum exceeds the median by more than 20%; inspect the retained observations.
- pyperf literal-skewed/match: CV 11.355% exceeds the analyzer's descriptive 10% flag.
- pyperf literal-skewed/match: maximum exceeds the median by more than 20%; inspect the retained observations.
- pyperf tuple-mixed/match: maximum exceeds the median by more than 20%; inspect the retained observations.
- pyperf dataclass-skewed/match: CV 18.789% exceeds the analyzer's descriptive 10% flag.
- pyperf dataclass-skewed/match: maximum exceeds the median by more than 20%; inspect the retained observations.
- pyperf literal-skewed/if: maximum exceeds the median by more than 20%; inspect the retained observations.
- pyperf tuple-skewed/if: maximum exceeds the median by more than 20%; inspect the retained observations.

Evidence input hashes:

| File | SHA-256 |
| --- | --- |
| match-final-dispatch-measured.json | 75882bfc1a16069f9b1c70c750d91067d7e54837c9eb574c46986be49d751050 |
| match-final-pyperf-manifest.json | e70754008ef5bd13eba60c8ac67d973ae22cc79ac3659630d8fd6f8470d6a7af |
| match-final-pyperf-match.json | 5d770fe8e8233417d0bceffffd58b9db8e807b54ccbfed5e08d16c14e11f0382 |
| match-final-pyperf-if.json | 0d19e78b6c2162e446db443c07fcd44b01ed71c8c7520abf2c2a35eb6db59d6e |

## Preserved initial baseline

Recorded commit: `620c35f42d8c35d7a27341bbe4ba259b043b959d`. Measured modes: aot, cpython, jit.

### Kernel timings

| Cell | Mode | Match median ms | If median ms | If/match median | Observed pair span | Pairs | CV match / if |
| --- | --- | --- | --- | --- | --- | --- | --- |
| literal-mixed | cpython | 1204.584 | 1107.489 | 0.922 | 0.890–0.958 | 7 | 2.2% / 1.6% |
| literal-mixed | jit | 13.315 | 16.348 | 1.226 | 1.151–1.299 | 7 | 1.6% / 2.7% |
| literal-mixed | aot | 12.498 | 13.774 | 1.106 | 0.998–1.249 | 7 | 3.9% / 5.5% |
| literal-skewed | cpython | 446.183 | 393.058 | 0.890 | 0.840–0.971 | 7 | 1.8% / 3.5% |
| literal-skewed | jit | 9.314 | 12.495 | 1.350 | 1.273–2.142 | 7 | 4.4% / 22.2% |
| literal-skewed | aot | 8.087 | 8.041 | 0.977 | 0.883–1.258 | 7 | 5.9% / 7.4% |
| tuple-mixed | cpython | 1443.783 | 761.241 | 0.527 | 0.517–0.568 | 7 | 2.4% / 2.8% |
| tuple-mixed | jit | 47.566 | 12.208 | 0.254 | 0.232–0.294 | 7 | 3.6% / 6.3% |
| tuple-mixed | aot | 12.721 | 13.315 | 1.007 | 0.983–1.079 | 7 | 3.4% / 1.9% |
| tuple-skewed | cpython | 1120.914 | 695.005 | 0.630 | 0.579–0.721 | 7 | 5.0% / 7.2% |
| tuple-skewed | jit | 36.072 | 12.124 | 0.321 | 0.236–0.490 | 7 | 15.9% / 15.8% |
| tuple-skewed | aot | 8.840 | 11.838 | 1.339 | 1.227–1.450 | 7 | 4.6% / 4.0% |
| dataclass-mixed | cpython | 3373.075 | 910.895 | 0.268 | 0.239–0.311 | 7 | 9.6% / 8.4% |
| dataclass-mixed | jit | 72.286 | 14.443 | 0.224 | 0.148–0.278 | 7 | 19.6% / 16.4% |
| dataclass-mixed | aot | 13.249 | 17.321 | 1.307 | 1.131–1.602 | 7 | 7.4% / 8.7% |
| dataclass-skewed | cpython | 2577.159 | 748.562 | 0.292 | 0.232–0.337 | 7 | 9.3% / 5.6% |
| dataclass-skewed | jit | 45.525 | 20.393 | 0.448 | 0.417–0.548 | 7 | 1.4% / 9.3% |
| dataclass-skewed | aot | 12.085 | 10.605 | 0.923 | 0.712–1.085 | 7 | 19.7% / 18.5% |

### AOT whole-command pyperf

| Cell | If/match ratio of means | If/match ratio of medians |
| --- | --- | --- |
| literal-mixed | 1.066 | 1.061 |
| literal-skewed | 1.040 | 1.028 |
| tuple-mixed | 1.221 | 1.060 |
| tuple-skewed | 1.276 | 1.312 |
| dataclass-mixed | 1.191 | 1.199 |
| dataclass-skewed | 0.898 | 0.895 |

### Recorded identities

| Item | Recorded value |
| --- | --- |
| Compiler command | ["/workspace/scratch/0bc6e8bc1edf/match-main/pystachy"] |
| Compiler executable SHA-256 | 4b8df6bceb078a25130d98006ed0831d03f9381b9c7ec74f61ec2ad95fd6ce02 |
| AOT executable SHA-256 | d95ef2725651c0b377ee5315a97d8943d05dd2e8bb61aa7f304690ccf0e53573 |
| Source manifest SHA-256 | da1220a7ac3a14bdd40f1edfaddfac31ff7866d1c95353902e823cb255b1f1f6 |
| Source files | 161 |
| Workload source SHA-256 | 98bd8300b8221557c1c0a10441d706f1260416ad1732c16344688581fa381e55 |
| CPU / affinity | INTEL(R) XEON(R) PLATINUM 8573C / [0] |
| CPython | 3.13.16 (main, Oct 14 2026, 01:04:01) [Clang 23.1.3 ] |
| pyperf | 2.11.0 |

Identities are copied from the measurement records; the analyzer does not inspect current compiler/source files. The full source-hash map remains in the controller report, and its canonical hash is recorded above.

### Dispersion and evidence cautions

- kernel literal-skewed/jit/match: median below 10 ms; short timing samples are sensitive to scheduling noise.
- kernel literal-skewed/jit/if: CV 22.242% exceeds the analyzer's descriptive 10% flag.
- kernel literal-skewed/jit/if: maximum exceeds the median by more than 20%; inspect the retained observations.
- kernel literal-skewed/aot/match: median below 10 ms; short timing samples are sensitive to scheduling noise.
- kernel literal-skewed/aot/if: median below 10 ms; short timing samples are sensitive to scheduling noise.
- kernel tuple-skewed/jit/match: CV 15.897% exceeds the analyzer's descriptive 10% flag.
- kernel tuple-skewed/jit/match: maximum exceeds the median by more than 20%; inspect the retained observations.
- kernel tuple-skewed/jit/if: CV 15.813% exceeds the analyzer's descriptive 10% flag.
- kernel tuple-skewed/jit/if: maximum exceeds the median by more than 20%; inspect the retained observations.
- kernel tuple-skewed/aot/match: median below 10 ms; short timing samples are sensitive to scheduling noise.
- kernel dataclass-mixed/jit/match: CV 19.589% exceeds the analyzer's descriptive 10% flag.
- kernel dataclass-mixed/jit/match: maximum exceeds the median by more than 20%; inspect the retained observations.
- kernel dataclass-mixed/jit/if: CV 16.356% exceeds the analyzer's descriptive 10% flag.
- kernel dataclass-mixed/jit/if: maximum exceeds the median by more than 20%; inspect the retained observations.
- kernel dataclass-skewed/cpython/match: maximum exceeds the median by more than 20%; inspect the retained observations.
- kernel dataclass-skewed/jit/if: maximum exceeds the median by more than 20%; inspect the retained observations.
- kernel dataclass-skewed/aot/match: CV 19.656% exceeds the analyzer's descriptive 10% flag.
- kernel dataclass-skewed/aot/match: maximum exceeds the median by more than 20%; inspect the retained observations.
- kernel dataclass-skewed/aot/if: CV 18.500% exceeds the analyzer's descriptive 10% flag.
- kernel dataclass-skewed/aot/if: maximum exceeds the median by more than 20%; inspect the retained observations.
- pyperf tuple-mixed/if: CV 26.827% exceeds the analyzer's descriptive 10% flag.
- pyperf tuple-mixed/if: maximum exceeds the median by more than 20%; inspect the retained observations.

Evidence input hashes:

| File | SHA-256 |
| --- | --- |
| match-dispatch-measured.json | 3f7ea1669ecbc2c5639c3b3fe6131e24e75de31a89d31700c4da045545601042 |
| match-pyperf-manifest.json | 74e442ed76025ce7aa01ee38645e7fbbd2d43bd40c020eb0d4a38a825cf18c7e |
| match-pyperf-match.json | 71be71fbec0c6eedfb7448e510554d4e4bdbcd8cea0f417ef0a2870412b12721 |
| match-pyperf-if.json | edd1863686487d9d57e92dca1356667723d8c27783998464ebac8ad9af27f43f |

## Baseline versus primary native kernels

Descriptive comparison of separate sessions, normalized by dispatch count; not a paired before/after experiment or confidence interval.

| Cell | Mode | Baseline if/match | Primary if/match | Baseline/primary match per dispatch | Baseline/primary if per dispatch |
| --- | --- | --- | --- | --- | --- |
| literal-mixed | jit | 1.226 | 1.119 | 1.060 | 1.148 |
| literal-mixed | aot | 1.106 | 1.340 | 0.883 | 0.720 |
| literal-skewed | jit | 1.350 | 1.109 | 1.144 | 1.357 |
| literal-skewed | aot | 0.977 | 1.899 | 0.972 | 0.508 |
| tuple-mixed | jit | 0.254 | 0.474 | 1.722 | 0.953 |
| tuple-mixed | aot | 1.007 | 1.077 | 0.831 | 0.808 |
| tuple-skewed | jit | 0.321 | 0.632 | 1.880 | 1.003 |
| tuple-skewed | aot | 1.339 | 1.060 | 0.873 | 1.113 |
| dataclass-mixed | jit | 0.224 | 0.536 | 2.597 | 0.967 |
| dataclass-mixed | aot | 1.307 | 0.886 | 0.831 | 1.206 |
| dataclass-skewed | jit | 0.448 | 0.496 | 1.925 | 1.684 |
| dataclass-skewed | aot | 0.923 | 1.106 | 1.153 | 0.915 |

## Diagnostic pilot: match-right-association-pilot.json

Short diagnostic native-JIT kernel pilot. Baseline compiler native; trial compiler CPython-hosted. Process wall times are not comparable. These results do not replace final native qualification.

| Cell | Pairs | Baseline/trial match median | Observed span | Trial if/match median |
| --- | --- | --- | --- | --- |
| tuple-mixed | 3 | 1.798 | 1.595–1.905 | 0.471 |
| tuple-skewed | 3 | 1.856 | 1.838–2.080 | 0.673 |
| dataclass-mixed | 3 | 2.105 | 2.033–2.247 | 0.504 |
| dataclass-skewed | 3 | 1.998 | 1.987–2.359 | 0.513 |
