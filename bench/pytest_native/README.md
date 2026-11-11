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
[upstream parity qualification](../../docs/pytest-native.md), and are not a claim
that the complete upstream pytest, JSON repair or CPython suite compiles. Both
CPython and native runs use Pystachy's maintained JSON repair port, preserving the
same application source while comparing runner/runtime costs.

## Reproduce

Use the pinned development Python and pytest from `tools/requirements-dev.txt`,
and a native compiler built from the current sources. See
[installation](../../docs/install.md). From the repository root:

```sh
python3 bench/pytest_native/bench.py \
  --python "$(command -v python3)" --compiler "$PWD/pystachy" \
  --samples 5 --work-dir build/pytest-benchmark-run \
  --json bench/pytest_native/results/local.json \
  --markdown bench/pytest_native/results/local.md
```

The work directory must be new. Repeat `--suite` to select subsets. The controller
pins itself and its children to the first allowed CPU on Linux, or an explicit
`--cpu`. It measures one process at a time; do not run other builds or benchmarks
concurrently. `--timeout` bounds each subprocess (default 180 seconds). Three
samples is the minimum; five or more is preferable. This is not a CI timing gate.

The JSON retains every raw sample, command, input/source/compiler hash, case ID,
phase outcome, output checksum, environment, load average and first-command
build/run measurement. The Markdown is generated from that data. An interrupted,
failed or incomplete run is marked incomplete and does not produce a complete
report. Replay on an otherwise idle host before presenting small differences.

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
  comparison enabled and program caching enabled. First use has an empty private
  Pystachy cache. The unchanged rerun uses that cache. An edit changes both the
  executed checksum and its assertion by one at the same source/work paths, so a
  stale executable fails validation. AOT mode rebuilds on each CLI invocation.

Each sample must exit successfully, execute the exact checksum inventory, and
report the exact passed count. Generated execution also validates all three
setup/call/teardown events per case. No skipped or xfailed case can count toward
the benchmark. All three full commands compare original pytest outcomes before
any interleaved timings begin. These qualification calls are not included in the
ordinary-pytest timing headline; their total elapsed times are retained.

The sampled variants are shuffled within each round using a recorded seed.
Report medians, p10–p90, min/max and sample counts; no combined average is useful
across these workloads. `wait4` supplies peak individual-process RSS, including
waited-for children. This is not peak simultaneous process-tree memory. A cold
cache means an empty private Pystachy cache; OS page caches and installed Python
bytecode caches are not flushed.

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
