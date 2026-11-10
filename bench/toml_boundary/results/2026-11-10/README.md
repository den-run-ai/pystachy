# Regex and date numbers as values

This compares baseline `04860a83618e744c6f461761b6ee7fdbbe21f985` (main) with
[candidate `b2647179`](https://github.com/den-run-ai/pystachy/commit/b2647179a5f4f2ab95932e5b23a0328e5a6b4b07).
The candidate makes lib's `re`, its engine and matcher module, and `datetime`
[numeric-value modules](../../../../docs/dynamic-any.md#numeric-value-modules):
they no longer track numeric identity. TOML's own modules, `functools` and
`string` still do; the consumer's own module does not opt in. Both checkouts
were committed and clean when measured; the [raw report](report.json) records
their revisions, source manifests, commands and samples.

## Workload and execution costs

Linux x86-64, Intel Xeon Processor @ 2.10GHz, one allowed CPU (0), LLVM 18.1.3.
CPython 3.13.18 hosted both compilers and supplied the oracle; the pinned
3.13.16 was not installed on this host. The consumer and parameters match the
[2026-11-09 run](../2026-11-09/README.md): 16 worker sections, five alternating
baseline/candidate processes, each running three samples of 100 parses, each
checked against CPython and an independent checksum.

Entries are medians across five processes. In-process durations first take the
median of each process's three samples.

| Cost | Baseline | Candidate |
|---|---:|---:|
| Hosted frontend IR emission | 2.238 s | 1.947 s |
| Warm AOT build | 12.991 s | 10.221 s |
| Whole-process JIT, compilation included | 4.882 s | 4.071 s |
| Whole-process AOT, three samples | 138.19 ms | 111.93 ms |
| JIT parsing/processing, 100 parses | 52.36 ms | 38.86 ms |
| AOT parsing/processing, 100 parses | 40.47 ms | 30.91 ms |
| First AOT build, empty runtime cache (one observation) | 21.485 s | 18.697 s |
| Executable bytes | 749,992 | 635,280 |

All five paired AOT comparisons improved; the median paired speed ratio is
1.309 (process medians 39.05–44.80 ms before, 30.11–33.55 ms after). Four of
five JIT pairs improved, with a median ratio of 1.378; one candidate process
measured 61.00 ms against its baseline's 57.34 ms, while the other four spanned
36.62–41.31 ms. Compile and build ranges do not overlap, but this is a shared
host: treat the timings as one workload's evidence, not a general claim.

## Allocations, retention and emitted operations

The counted AOT build runs the same three samples (300 parses). Counts are C
allocation requests before allocator rounding, including initialization and
output; the live-byte diagnostic retains the input and one document after 100
parses, in five independent processes.

| Metric | Baseline | Candidate | Interpretation |
|---|---:|---:|---|
| C allocation requests | 3,572,770 | 3,099,744 | 13.2% fewer |
| C requested bytes | 179,776,508 | 130,039,189 | 27.7% fewer |
| `memcpy` calls | 1,071,704 | 672,064 | 37.3% fewer |
| Collections | 5 | 4 | |
| Peak managed-heap bytes | 36,450,304 | 35,913,728 | 1.5% lower |
| Conservative post-collection live bytes | 143,425 | 109,104 | Identical in all five processes per variant |
| Raw program IR lines | 91,173 | 68,906 | Static footprint |
| Raw C dynamic-helper call sites | 2,000 | 572 | Direct `pys_dyn_*` calls |
| Raw list identity-helper call sites | 386 | 17 | `pys_list_*identity` |
| Raw generated-dispatcher call sites | 24 | 24 | Direct `dyn.*` calls |
| LLVM-O2 program IR lines | 53,517 | 50,601 | Before runtime linking |
| LLVM-O2 C dynamic-helper call sites | 1,695 | 591 | Static calls, not execution counts |

Most removed helper calls are `pys_dyn_int_box` (1,228 to 120 raw sites): the
regex engine and date code no longer box numbers for companion slots. The
collector is conservative, so the live-byte total is not an object census; it
includes globals, caches, input and conservatively retained objects.

## Correctness and scope

The new [differential case](../../../../tests/programs/inference/dynany_identity_values.py)
records CPython's results for regex positions, date and duration fields, module
variables, named tuples and `re.error`. The baseline compiler gives the opposite
answer for the four position and field identities; the candidate matches.
Compiling the corpus with both compilers reading the candidate's library, 19 of
4,396 programs differ: the dynamic programs that reach `re` or `datetime`. The
other 4,377 are byte-identical, including every program without dynamic `Any`.
Those 19 pass JIT and AOT, normally and with a collection at every allocation
(76 executions).

Fixed points, the IR check on the 19 programs, lint, `make check-fast` and the
identity-scope tests passed locally. Full verification is CI's evidence.

```sh
python3.13 bench/toml_boundary/run.py --baseline BASELINE --candidate CANDIDATE \
  --output NEW_DIR --width 16 --rounds 100 --processes 5 --samples 3
```

Short-use and input-size scaling remain unmeasured.
