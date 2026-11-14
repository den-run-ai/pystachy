# Locally caught container errors: 2026-11-11

## Source and method

Baseline: `0ec827ac34837cc917627e1ce594c484db6e9227` (main).
Measured local candidate: `5cc4fd5ad64cf5e7ede2a7586047ba6266a6e8f4`.
Published [candidate source](https://github.com/den-run-ai/pystachy/commit/570d918e338313ed4b91c17d573c4ae53fbd137b)
has the identical Git tree `e2097d04809228e7dc972ef5e67502e4e2335a03`.
The [source map](source-map.json) records local/published identities for both designs;
commit metadata differs, but tracked file contents and modes match exactly.
Both checkouts were clean and unchanged throughout the run. Later changes in this
PR only record these results. [results.json](results.json) contains every timing,
checksum, source/compiler/executable hash, build command and environment setting.

Linux 6.18.57, x86-64, Intel Xeon Platinum 8573C; CPython 3.13.16; LLVM/Clang
18.1.3. AOT used `PYSTACHY_AOT_OPT=2`, each compiler's own runtime/library and CPU
0 affinity. Seven samples per variant rotate CPython/baseline/candidate order.
Correctness is checked against CPython before timing and in every timed sample.
No other task build or test ran concurrently. This is a shared host: load averages
were 2.34/2.78/2.53 before and 2.22/2.62/2.50 after the run; scheduling noise remains.

Run from the candidate checkout after building both compilers:

```sh
python3.13 bench/local_exceptions/run.py \
  --baseline ../baseline --candidate . --python python3.13 \
  --llvm /path/to/llvm-18/bin --cpu 0 --repeats 1000 \
  --hit-multiplier 100 --samples 7 \
  --output build/local-exceptions-final/results.json
```

The recorded JSON retains the exact interpreter and toolchain paths used here.
See the [workload guide](../../README.md) for setup and timer boundaries. Each
batch has 512 lookups; mixed cases miss on half of them in consecutive groups,
not a random sequence. Word count has 256 distinct strings repeated twice per
batch, including insertion after each first miss. All-hit cases run 100 times
more operations to make the short native loops measurable; compare variants
within a row, not raw all-hit and all-miss times.

## Results

Medians in seconds. The last column is baseline/candidate; below 1 means slower.

| Case | Lookups/operations | CPython | Baseline AOT | Candidate AOT | Median ratio |
|---|---:|---:|---:|---:|---:|
| `dict_hit` | 51,200,000 | 1.642114 | 0.326141 | 0.355909 | 0.92x |
| `dict_miss` | 512,000 | 0.071407 | 0.738551 | 0.088004 | 8.39x |
| `dict_mixed` | 512,000 | 0.040574 | 0.344598 | 0.050524 | 6.82x |
| `list_hit` | 51,200,000 | 2.119142 | 0.052430 | 0.046880 | 1.12x |
| `list_miss` | 512,000 | 0.078410 | 0.564651 | 0.046407 | 12.17x |
| `list_mixed` | 512,000 | 0.036148 | 0.249126 | 0.027024 | 9.22x |
| `word_count` | 512,000 | 0.057783 | 0.348202 | 0.052762 | 6.60x |
| `index_miss` | 512,000 | 0.207621 | 0.713756 | 0.702385 | 1.02x |
| `int_miss` | 512,000 | 0.319827 | 0.798593 | 0.844829 | 0.95x |

Dictionary misses improve 8.4x, list misses 12.2x, and the bounded word-count
consumer 6.6x. Mixed dictionary/list reads improve 6.8x/9.2x. This is steady-state
AOT workload time, not an application-wide or JIT-startup claim. Dictionary misses
still have a higher median than CPython; eager key representation is preserved.

The dictionary all-hit median is **9.1% slower**. Its baseline/candidate sample
ranges overlap, so this run does not establish the exact size of that cost.
The PR retains the observed hit-path tradeoff for review. List-hit and unchanged-path control ranges overlap too;
small median differences for those rows are inconclusive. `list.index()` and
`int()` were not optimized. Peak memory and allocation counts were not measured.

Observed minimum-maximum seconds (seven samples; not confidence intervals):

| Case | CPython range | Baseline range | Candidate range |
|---|---:|---:|---:|
| `dict_hit` | 1.597800-1.676423 | 0.305587-0.358010 | 0.339241-0.401728 |
| `dict_miss` | 0.062296-0.134040 | 0.684068-1.299757 | 0.081650-0.123795 |
| `dict_mixed` | 0.036093-0.049310 | 0.316744-0.401328 | 0.047519-0.088522 |
| `list_hit` | 1.398157-2.330002 | 0.044245-0.098165 | 0.041214-0.075316 |
| `list_miss` | 0.057555-0.093463 | 0.448398-0.624626 | 0.040712-0.064832 |
| `list_mixed` | 0.035194-0.073635 | 0.227386-0.326628 | 0.025078-0.028501 |
| `word_count` | 0.054709-0.072621 | 0.334437-0.360481 | 0.050004-0.118857 |
| `index_miss` | 0.180152-0.219060 | 0.655101-0.916607 | 0.668426-0.739471 |
| `int_miss` | 0.291310-0.428395 | 0.772623-1.392879 | 0.780596-1.165309 |

## Earlier index-returning design

[initial-index-results.json](initial-index-results.json) preserves the first
complete run at local `c53f29e24e22f378d6c2fc9ac492fac4bca10cb4`
([identical published source](https://github.com/den-run-ai/pystachy/commit/c4639ec11c641f76a2d47824b216c961d6945fad)).
It returned a dictionary
entry index and loaded the value separately. Misses already improved 8.1x for
dictionaries and 10.9x for lists, while its short dictionary-hit median increased
from 0.003176 to 0.003747 seconds. That run used only 512,000 operations even for
all-hit cases, so it is not the final estimate of hit-path overhead. The final
design returns a value-slot address and uses the existing runtime value ABI for
an immediate guarded load; the table above uses longer hit loops.

## Validation

Validated implementation `5cc4fd5a` against baseline
`0ec827ac` with CPython 3.13.16 and LLVM 18.1.3 on Linux x86-64.
The [validation record](validation-summary.json) includes compiler hashes,
commands, exact test selections and every changed IR case with its rewrite counts.

| Check | Result |
|---|---|
| Compiler/runtime bootstrap | Three matching stages each; 899,620 compiler and 21,100 runtime IR lines |
| Fast tests and lint | 707 executed unit tests passed; 33 skipped; ruff, mypy, shellcheck and C warnings checks passed |
| Runtime signatures/effects and roots | 676 entries and 70 exception classes agree; 68 static pointer stores have no root problems |
| IR checker and LLVM assembler | 2,516 programs passed |
| Normal native correctness | 693 checks passed across 346 cases: 692 JIT/AOT runs and one syntax check |
| Selected GC stress / optimizations off | 26 checks passed in each configuration |
| Five changed benchmark sources | 15 CPython/JIT/AOT execution checks and five AOT builds passed |

The full 4,406-program IR comparison preserved all accept/reject decisions and
diagnostics. Exactly 177 cases changed IR. An independent structural audit accounted
for all 912 rewrites: 193 dictionary reads, eight dictionary-entry reads and 711 list
reads. Reversing the validated replacements reproduced all 303 changed function
instances, allowing generated SSA/block identifier renaming. All 169 changed executable
corpus cases ran in JIT and AOT; the five changed benchmark sources also matched
CPython. Both compilers retained their own libraries; only equal-length absolute
checkout prefixes were normalized, and only `runtime.c` differed among home inputs.

The 33 unit skips comprise 32 tests requiring the built Lean checker and one
retained-IR integration test requiring `PYSTACHY_TEST_LLVM`. Full `make verify` and
full `make check-recordings` were not run locally. Static IR auditing is additional
evidence, not a formal proof or a replacement for those remaining gates. Benchmark
correctness runs establish no speed result; timings are reported separately.

The implementation adds 146 net compiler/runtime lines.
