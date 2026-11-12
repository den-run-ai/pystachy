# Native pytest benchmark

This benchmark compares the same assertions in four executions: ordinary
CPython pytest, prepared generated code on CPython, native JIT and a prebuilt
native executable. It also measures the actual `tools/pytest_native.py` command
with its independent pytest oracle on a cold private cache, an unchanged rerun,
and a semantic edit/rebuild. The compiler and LLVM toolchain must already be
installed; compiler installation/bootstrap is outside the measured development
cycle.

| Suite | Cases | Runtime work |
|---|---:|---|
| `fixtures` | 16 | Four dependent fixtures, shared aliases, reverse yield cleanup and small assertions |
| `json_repair` | 8 | 1,000 repairs per case, including malformed objects, comments and Unicode |
| `numeric` | 4 | 20 × 20,000 integer checksum steps per case, with different seeds |

These are original benchmark tests of the maintained APIs. They supplement the
[upstream parity qualification](../../docs/pytest-native.md) and do not show that
the complete upstream pytest, JSON repair or CPython suite compiles. Both CPython
and native runs use Pystachy's maintained JSON repair port, preserving the same
application source while comparing runner/runtime costs.

## Historical alpha.3 Linux run: 11 November 2026 (UTC)

The [measurement report](results/2026-11-11.md) and
[raw JSON](results/2026-11-11.json) contain seven interleaved samples of every
execution, plus the complete first-command, unchanged-rerun and edit/rebuild
measurements. All 84 comparative samples and 36 full lifecycle commands passed
their exact inventories and checksums. The measured source was the clean tree at
[`7e33fb336a6429caf089aff3bd5c684528202c26`](https://github.com/den-run-ai/pystachy/commit/7e33fb336a6429caf089aff3bd5c684528202c26).

These are historical alpha.3 measurements, not measurements of alpha.4, alpha.5 or
the updated harness. New performance claims about the released code require a
fresh run with a matching compiler.

The unchanged schema 2 JSON retains full lifecycle phase events, but the harness
validated and then discarded the phase events of the comparative generated samples
and JIT warmups; their stdout checksums and completion status remain independently
inspectable. The JSON also omits a source hash for `lljit.c` and fingerprints for
`llvm-as`, `llvm-link`, `lli` and the selected `libLLVM`, so its native provenance
is incomplete. Those missing records have not been reconstructed or backfilled.
The current schema 3 harness retains the phase events and expanded native
provenance for future runs.

Preparation alone reduced the median CPython time by 5.76× for fixtures, 1.37×
for JSON repair and 2.00× for the numeric workload. Reusing a prebuilt AOT
executable gave a further 10.05×, 4.65× and 28.29× respectively over prepared
CPython. Against ordinary pytest, the corresponding AOT ratios were 57.85×,
6.39× and 56.52×. These ratios describe different workloads; they have no useful
combined average. The fixture result mainly measures startup and dispatch,
JSON repair performs 8,000 actual repairs, and the numeric result measures a
typed integer-loop kernel with runtime bounds and seeds.

The full default CLI runs an independent CPython oracle on every invocation.
Its unchanged commands remained slower than ordinary pytest in every measured
mode, including confirmed JIT cache hits. Native first commands took 10.7–20.4
seconds across these suites and modes. These measurements therefore support
prebuilt execution and prepared-dispatch gains, not a claim that every complete
development command becomes faster.

Memory is workload-dependent too. Prebuilt AOT peaked at 1.5 MiB for fixtures
and 1.3 MiB for numeric work, but 34.2 MiB for JSON repair, versus 29.9 MiB for
ordinary pytest and 15.3 MiB for prepared CPython on that JSON workload. Standalone
cold AOT builds peaked at 123.0–157.6 MiB. The report includes preparation and every full
command's memory, as well as execution peaks.

### What the break-even estimates mean

| Repeated unchanged workload | Fixtures | JSON repair | Numeric |
|---|---:|---:|---:|
| Manual preparation/build, then direct AOT reuse; excludes qualification | 62 runs | 45 runs | 27 runs |
| First qualified AOT CLI command, then direct executable reuse; estimate | 66 runs | 47 runs | 31 runs |
| Invoke the full qualified CLI on every run | No observed saving | No observed saving | No observed saving |

The second row is an inference from the recorded full first AOT command and the
prebuilt execution distribution, assuming equivalent unchanged generated code and
per-run performance. The full CLI and standalone preparation produce
byte-identical test modules with different entry drivers; this row estimates
comparable direct execution. Its calculation is
`ceil((first_aot - median_aot) / (median_pytest - median_aot))`: the first command
includes preparation, compilation, execution and its CPython oracle; later runs
reuse the executable directly, whereas the actual full AOT CLI rebuilds on every
invocation.

The first command and build costs are single observations, while execution medians
use seven samples. These estimates need confirmation on the intended development
machine, especially when edits are frequent.

### Recorded compiler and replay

This run used CPython 3.13.16, pytest 9.2.0, LLVM/Clang 18.1.3 and the Linux
x86_64 native compiler from
[`v0.4.0-alpha.3`](https://github.com/den-run-ai/pystachy/releases/tag/v0.4.0-alpha.3).
Its release manifest identifies source commit
`c5cebb8bdeb71e7e099b48e4400119dd1e5b29e2`; its executable SHA-256 is
`65657dda88dfb5e8faa92a88db2982f81e7fd6fd68abb7bb7f7260e4d3bb9e5b`.
The compiler, runtime and library sources are unchanged between that release
commit and the measured revision, verified with:

```sh
git diff --exit-code c5cebb8bdeb71e7e099b48e4400119dd1e5b29e2 \
  7e33fb336a6429caf089aff3bd5c684528202c26 \
  -- src pystachy.py lib runtime.py runtime.c lljit.c ryu mpz
```

To replay this revision, check it out in a separate clean worktree and use the
pinned interpreter, compiler and LLVM installation. For example, after setting
these three paths:

```sh
BENCH_PYTHON=/absolute/path/to/python3.13.16
BENCH_COMPILER=/absolute/path/to/alpha.3/libexec/pystachy/pystachy
BENCH_LLVM=/absolute/path/to/llvm-18/bin
git checkout 7e33fb336a6429caf089aff3bd5c684528202c26
env -u LD_LIBRARY_PATH PYSTACHY_LLVM="$BENCH_LLVM" \
  "$BENCH_PYTHON" bench/pytest_native/bench.py \
  --python "$BENCH_PYTHON" --compiler "$BENCH_COMPILER" \
  --samples 7 --order-seed 20261110 --cpu 0 \
  --work-dir build/pytest-benchmark-replay \
  --json bench/pytest_native/results/replay.json \
  --markdown bench/pytest_native/results/replay.md
```

CPU 0 was the recorded affinity; select an allowed CPU on other hosts. This
toolchain ran without `LD_LIBRARY_PATH`. A nonempty custom loader environment
can bypass the native program cache: the report records observed cache events,
not just the requested setting. Each measured suite showed first-run
`miss → stored`, unchanged `hit`, and edited `miss → stored`.

The host was shared, so distributions and outliers are retained. All timings
include the same measurement launcher; no overhead was subtracted. These are
28 original benchmark cases, separate from the 69 selected upstream cases
qualified by the upstream tools. Complete upstream compatibility is outside
the scope of either result.

## Reproduce

Use the pinned development Python and pytest from `tools/requirements-dev.txt`,
and a native compiler built from the current sources. See
[installation](../../docs/install.md). From the repository root:

```sh
python3 bench/pytest_native/bench.py \
  --python "$(command -v python3)" --compiler "$PWD/pystachy" \
  --samples 7 --order-seed 20261110 --work-dir build/pytest-benchmark-run \
  --json bench/pytest_native/results/local.json \
  --markdown bench/pytest_native/results/local.md
```

The work directory must be new. Repeat `--suite` to select subsets. The controller
pins itself and its children to the first allowed CPU on Linux, or an explicit
`--cpu`. It measures one process at a time; do not run other builds or benchmarks
concurrently. `--timeout` bounds each subprocess (default 180 seconds). Three
samples is the minimum; five or more is preferable. This is not a CI timing gate.

Schema 3 JSON retains every raw sample, command, input/source/compiler/sampler
hash, output checksum, environment, load average and first-command build/run
measurement. Every generated sample and JIT warmup retains its validated case
IDs and setup/call/teardown events; full lifecycle commands retain their generated
and original-pytest evidence. LLVM tool fingerprints follow the compiler's actual
selection of `clang`, `opt`, `llvm-as`, `llvm-link` and `lli`. On Linux, a bounded
`ldd` lookup records the selected `libLLVM` mapping and hash when available, or an
explicit unresolved status. This records native inputs, not which JIT launcher
executed. Source hashes include `lljit.c`; source/tool/library identities are
compared again before marking the report complete.

The Markdown is generated from the new data. Before compilation or provenance
checks begin, both output paths are replaced with incomplete reports, so a startup
failure cannot leave an earlier success labeled as the current attempt. An
interrupted, failed or incomplete run does not produce a complete report. Replay
on an otherwise idle host before presenting small differences.

## Timing boundaries

- **Ordinary pytest:** a fresh process using the standard CLI with `-q -s`, normal
  assertion rewriting, plugin autoload disabled, no conftest/configuration and no
  custom diagnostic reporting plugin. `-s` exposes the same small checksum output
  checked for the other executions. Collection and fixture dispatch are included.
- **Generated CPython:** a fresh process running prepared generated code. The
  separately measured preparation covers interpreter startup, collection,
  generation and copying the runner support module.
- **Native JIT:** a fresh compiler process that compiles and executes the
  generated suite. Program caching is disabled for these interleaved samples;
  runtime caching is warm. A separate validated JIT execution populates any
  JIT-only runtime object, shared runtime and launcher after the AOT build; its
  time and resource cost are retained. Cold first-command costs appear separately.
- **Prebuilt AOT:** a fresh process running the prebuilt executable. Preparation
  and the cold-cache AOT build are reported separately and included in break-even
  calculations. This is the repeated-run comparison, not first-command speed.
- **Full command:** the actual generated-runner CLI, with original pytest
  comparison enabled and program caching requested. Cache traces establish whether
  it misses, hits or bypasses; enabled settings alone do not prove a cache hit.
  Trace output is enabled only for lifecycle commands and its small cost is included.
  First use has an empty private
  Pystachy cache. The unchanged rerun uses that cache. An edit changes both the
  executed checksum and its assertion by one at the same source/work paths, so a
  stale executable fails validation. The JSON's `edit_baseline` records the
  command that warms the temporary copy at that path before the edit. AOT mode
  rebuilds on each CLI invocation.

All measured commands use the same tiny native measurement launcher. It forks the
target after its own exec, removing the Python controller's inherited RSS floor
from target memory accounting. Elapsed times include launcher startup, fork and
reporting overhead, which is not subtracted and matters proportionally most for
the tiny AOT suite; the launcher's one-time compilation is outside the timings.
The JSON pins its C source, executable, compilation command and compiler.

Each sample must exit successfully, execute the exact checksum inventory, and
report the exact passed count. Generated execution also validates all three
setup/call/teardown events per case. No skipped or xfailed case can count toward
the benchmark. All three full commands compare original pytest outcomes before
any interleaved timings begin. These qualification calls are not included in the
ordinary-pytest timing headline; their total elapsed times are retained.

The sampled variants are shuffled within each round using a recorded seed. Report
medians, p10–p90, min/max and sample counts; no combined average is useful across
these workloads. A cold cache means an empty private Pystachy cache; OS page
caches and installed Python bytecode caches are not flushed.

The native launcher's `wait4` supplies the target's peak individual-process RSS,
including waited-for descendants, not peak simultaneous process-tree memory. The
outer launcher's RSS is retained separately. Preparation/build and all
full-command lifecycle peaks are reported too.

Retained-executable break-even amortizes preparation/build over direct AOT
executions. It does not describe repeatedly invoking the full runner CLI, which
also runs its original-pytest oracle and rebuilds in AOT mode. The report computes
a separate full-command estimate using first + unchanged reruns; no estimate is
reported when the measured unchanged CLI is slower than ordinary pytest. The
single first/unchanged/edit observations are not distributions.

## Inputs and expectations

Each test reads `PYTEST_BENCH_INPUT` at runtime. The input files are committed and
hashed; their values and bounds are not compiled into a program. JSON inputs and
expected serialized strings are tab-separated; numeric rows contain size,
rounds, seed and an independently calculated checksum. The checksum is equivalent
to this Python expression:

```python
sum(((index * 37 + seed + turn * 19) % 1009) ** 2
    for turn in range(rounds) for index in range(size)) % 1000000007
```

No Python integer in the numeric workload approaches the signed 64-bit limit.
JSON tests use the port's existing explicit dynamic-`Any` return contract; fixture
and numeric suites remain typed. Runtime inputs, assertions and checksum output
keep the work observable. `tools/test_pytest_native_benchmark.py` checks failure
controls, checksum/inventory rejection, input execution under real pytest and
generated CPython, and the semantic edit control.
