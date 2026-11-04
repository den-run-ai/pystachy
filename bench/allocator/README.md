# Allocator and collector workloads

Small programs that stress the collector's allocator in the ways the issues below measured,
and a controller that times them across runtime variants. The
[2 November 2026 evaluation](https://github.com/den-run-ai/pystachy/blob/a2cb8a3638d715577a7ab1cd1e4a0d6b01b6cdf2/docs/reports/allocator-prototype.md)
records the measurements and allocator decisions.

| Workload | Program | Stresses |
|---|---|---|
| `nodes` | [nodes.py](nodes.py) `200` | small pointer-bearing objects that die each step beside a small live set ([#650](https://github.com/den-run-ai/pystachy/issues/650)) |
| `vectors` | [vectors.py](vectors.py) `3000000` | small objects that hold no reference (`pys_new`), most elided, a quarter kept |
| `slice20k`, `slice4k` | [slice_tail.py](slice_tail.py) | `s[1:]` of 20 KB and 4 KB strings: large and medium pointer-free objects ([#127](https://github.com/den-run-ai/pystachy/issues/127)) |
| `chevron` | [chevron.py](chevron.py) `slice 400 1400` | a tokenizer cutting a 21 KB template: strings of every size, 1,193 collections ([#127](https://github.com/den-run-ai/pystachy/issues/127)) |
| `peak` | [peak.py](peak.py) `400 4000000` | 128 MiB live, 400 MiB of short-lived 1 MiB strings, then small strings ([#615](https://github.com/den-run-ai/pystachy/issues/615)) |
| `strbuild` | [strbuild.py](strbuild.py) `20000` | joins, splits, case maps and appends of 100 to 20,000-byte strings |
| `lists` | [lists.py](lists.py) `3000` | growing and copied lists of ints and lists, dicts of strs |

[run.py](run.py) also runs `bench/json_repair/bench.py`, `bench/words.py`,
`bench/dictcount.py`, `tools/dynany_bench.py graph-smoke` and, given its dataset,
150 steps of [microGPT](../microgpt/README.md). Each program reports the seconds of
its own loop (a `TIME` line on stderr, or the workload's own report), so start-up and
JIT compilation are outside that timer; wall time, peak RSS and minor page faults are
the whole process's (`getrusage`).

## Reproduce

Build the compilers to compare, for example `main` in another worktree and this
checkout, then interleave them (each round runs every variant once, in rotating order)
on an otherwise idle CPU:

```sh
python3 -I bench/allocator/run.py \
  --variant main=../main/pystachy:../main --variant proto=./pystachy:. \
  --rounds 5 --cpu 3 --tiers aot,jit --names /path/to/names.txt --json build/alloc.json
```

A variant `NAME=COMPILER[:HOME][+LIB]` builds with that compiler against the
`runtime.c` of `HOME` (`PYSTACHY_HOME`); `+LIB` preloads a C allocator such as
`libmimalloc.so` into each program (and, for `--tiers jit`, into `lli` and LLVM too)
and reuses the AOT builds of the variant before it. Every run's output must agree;
the summary marks a row whose output differs. Results are advisory: shared hosts are
noisy, and nothing here is a threshold.

## Allocator tradeoffs

The [runtime](../../docs/internals.md#values-and-runtime) manages its own heap. Its
page reuse and selective clearing address the page faults and redundant zeroing
identified by these workloads. Replacing the C allocator with mimalloc or jemalloc
therefore affects auxiliary allocations such as the page map, tables and file
buffers; it does not replace the collector's heap.

Retaining dirty free pages avoids faults in the next allocation cycle, but can keep
RSS near its peak between collections. Compare loop time, peak RSS and memory after
the live set shrinks when changing collection pacing or retention budgets
([#650](https://github.com/den-run-ai/pystachy/issues/650),
[#615](https://github.com/den-run-ai/pystachy/issues/615)). A faster allocation path
alone does not establish a better policy for every workload.

The [evaluation's remaining candidates](https://github.com/den-run-ai/pystachy/blob/a2cb8a3638d715577a7ab1cd1e4a0d6b01b6cdf2/docs/reports/allocator-prototype.md#6-follow-ups)
include avoiding a redundant clear for pointer-free arrays written in full and
internalizing runtime globals in AOT builds. The first requires an audit of readers
of spare list capacity; the second concerns AOT builds, where the JIT's exported
fast-path globals constrain optimization. The historical measurements provide comparison cases, not
performance thresholds.
