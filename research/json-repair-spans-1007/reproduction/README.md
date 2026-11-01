# Reproduce the ordinary-span comparison

This bundle recreates the paired baseline and candidate used to evaluate PR #1007.
The source preparation and build recipe is isolated in a new directory. The timed
campaign requires an explicit `--run`; preparing sources or building the compilers
does not start the benchmark campaign.

## Exact comparison

| Input | Pinned revision or identity |
| --- | --- |
| Main before the three PRs | `07b26e02425d023288ed95a9d2a5077be5aeb45e` |
| #1003: integer correctness and bounded repair recursion | `dceda23e8b71311c43e5c843698ed4443292004b` |
| #1004: bounded multi-byte JSON scanner | `d056aafe2f0c09d72ca23bf14b18123d1e439170` |
| #1007: final ordinary-span implementation/probe | `946bb203c1835af708b5779c388b85482cf7514b` |
| Combined #1003 + #1004 baseline Git tree | `276e01519733a14303e9d7d29bed2b44df92e37a` |

The baseline is a local merge of #1004 into #1003. The candidate starts with that
exact merged tree and applies **only** the `ports/json_repair/parse_string.py` diff
between main and the pinned #1007 commit. The benchmark probe comes unchanged from
#1007 and is compiled against each variant's own ports and libraries.

Do not replace the whole `ports/json_repair` directory with #1007's main-based
version. In particular, #1003's depth-management wrappers are in `json_parser.py`.
The script checks that baseline and candidate differ in exactly one file and that
`json_parser.py` remains byte-identical. The local merge and candidate commits use
neutral reproduction metadata. Their commit IDs can differ from the original
research checkout; the baseline tree and file hashes establish the source identity.

### Checked file hashes

| File | SHA-256 |
| --- | --- |
| Baseline `parse_string.py` | `caf4b7fff811df8e5e53a67720d231d1a4e2c1afa8d907be8e50c859341551df` |
| Candidate `parse_string.py` | `9193bc763e38bfeee444ea8778c203372c72174502ec480bc0ef83be7a02b4c5` |
| `bench/extended/json_repair_spans.py` from #1007 | `b89da4a79796a6ef780bb7a59babcad41284dad499d613b789d9326394b99e8d` |

The script fails if a pinned commit, merge tree, file hash, or candidate changed-file
set does not match. It records the patch hash, resulting candidate tree, local
commits, compiler/executable hashes, toolchain paths, commands, and logs.

## Prerequisites

Use Linux with `git`, GNU `make`, `/usr/bin/taskset`, and a complete LLVM 18
toolchain (`clang`, `lli`, `opt`, `llvm-link`, and `llc`). The recorded campaign used
LLVM/Clang 18.1.3. Use **CPython 3.13.16**, including for the reproduction driver;
the script rejects another Python version. No pip packages are required for the
compiler bootstrap or the benchmark probe. Installing packages or toolchains is
outside this script.

Both source trees are built afresh with `make`. This verifies the compiler's three
IR stages and the runtime's three IR stages before the probe is built. Keep ample
disk space for the independent checkouts, compiler intermediates, private runtime
caches, and raw benchmark records.

CPU 0 is the default, matching the original campaign. It must be in the process's
allowed affinity set. If a container does not expose CPU 0, choose an available CPU
explicitly using `--cpu N`. That is a different placement, recorded in the result;
do not describe measurements from another host/CPU as identical to the original.
Run timing only after other builds, test suites, and CPU-intensive jobs have stopped.

## Prepare and build without timing

Place the four bundle files together: `reproduce.py`, `reproduce.sh`,
`run_benchmarks.py`, and `runner-provenance.json`. Set the Python executable to your
actual CPython 3.13.16 installation and the LLVM path to its complete `bin` directory:

```bash
export PYSTACHY_SPAN_PYTHON=/absolute/path/to/python3.13
export PYSTACHY_LLVM=/usr/lib/llvm-18/bin
bash reproduce.sh --dest /tmp/pystachy-spans-reproduction
```

The destination must not exist. To allocate a fresh retained temporary directory,
omit `--dest`; its path is printed immediately. The script's source changes and
build artifacts are isolated under that destination. Existing repositories are
not edited. There are no remote pushes, force operations, user sign-offs, or
changes to global Git configuration. Failures retain their directory and command logs.

Git operations retain the caller's installed hook and signing policies; the script
does not override `core.hooksPath`, `commit.gpgsign`, or `tag.gpgsign`. Local commits
use neutral reproduction author metadata while respecting those policies. A hook
or signing failure stops the recipe and is retained in its log. Repository-routing
environment variables are removed so they cannot redirect the isolated Git
commands into another working tree or index; configuration and signing environment
variables are preserved. The pinned tree and file checks reject changes to the
compared tracked sources, including changes made by an installed hook.

The script fetches only the histories needed for the four exact commits from the
public repository. `--repo /path/to/a/local/mirror` can supply an existing mirror
that contains those commits. The fetched source store and every working checkout
are still created inside the new destination.

To inspect the reconstructed sources without compiling anything:

```bash
bash reproduce.sh --dest /tmp/pystachy-spans-source-review --prepare-only
```

`--prepare-only` cannot be combined with `--run`. A separate fresh invocation is
needed for the default build workflow; the script intentionally does not reuse or
clean an existing destination.

## Run the paired campaign explicitly

After the normal build invocation completes, it prints the exact environment file
and runner paths. For the explicit destination above:

```bash
source /tmp/pystachy-spans-reproduction/span-evidence/reproduction-env.sh
"$PYSTACHY_SPAN_PYTHON" "$PYSTACHY_SPAN_ROOT/span-evidence/run_benchmarks.py"
```

This prints the plan only. Start measurements with:

```bash
"$PYSTACHY_SPAN_PYTHON" "$PYSTACHY_SPAN_ROOT/span-evidence/run_benchmarks.py" --run
```

Alternatively, opt in at the initial invocation to prepare, build, and then run:

```bash
bash reproduce.sh --dest /tmp/pystachy-spans-full-run --run
```

The default results directory is `span-evidence/paired-native`. The runner refuses
to overwrite it. Use `--output /absolute/path/to/a/new/results-directory` for a
separate repeated campaign. `PYSTACHY_SPAN_ROOT` is mandatory for this portable
runner; it has no fallback to the original session's filesystem.

## Layout and build commands

The generated layout preserves the runner's expected names:

```text
pystachy-combined-base/                 merged #1003 + #1004
pystachy-combined-candidate/            that merge plus only the span parser diff
pystachy-spans/                        pinned #1007 checkout providing the probe
span-evidence/bench-base               baseline AOT probe
span-evidence/bench-candidate-fast      final candidate AOT probe
span-evidence/run_benchmarks.py         portable runner
span-evidence/reproduction-env.sh       explicit root, Python, LLVM, CPU
span-evidence/reproduction-metadata.json
span-evidence/reproduction-commands.json
span-evidence/reproduction-logs/
span-evidence/paired-native/            created only when timing is requested
```

For each variant, the driver runs a fresh `make PY=/absolute/path/to/python3.13`,
then the equivalent of:

```bash
PYSTACHY_HOME="$PYSTACHY_SPAN_ROOT/pystachy-combined-base" \
PYSTACHY_PATH="$PYSTACHY_SPAN_ROOT/pystachy-combined-base/ports" \
PYSTACHY_CACHE="$PYSTACHY_SPAN_ROOT/span-evidence/build-cache-base" \
"$PYSTACHY_SPAN_ROOT/pystachy-combined-base/pystachy" build \
  "$PYSTACHY_SPAN_ROOT/pystachy-spans/bench/extended/json_repair_spans.py" \
  -o "$PYSTACHY_SPAN_ROOT/span-evidence/bench-base"

PYSTACHY_HOME="$PYSTACHY_SPAN_ROOT/pystachy-combined-candidate" \
PYSTACHY_PATH="$PYSTACHY_SPAN_ROOT/pystachy-combined-candidate/ports" \
PYSTACHY_CACHE="$PYSTACHY_SPAN_ROOT/span-evidence/build-cache-candidate" \
"$PYSTACHY_SPAN_ROOT/pystachy-combined-candidate/pystachy" build \
  "$PYSTACHY_SPAN_ROOT/pystachy-spans/bench/extended/json_repair_spans.py" \
  -o "$PYSTACHY_SPAN_ROOT/span-evidence/bench-candidate-fast"
```

The driver supplies a clean build/benchmark environment and the selected `PYSTACHY_LLVM`.
The manual commands above assume the generated environment file was sourced;
inherited `PYSTACHY_*` optimization/GC overrides must not be added to a comparison.

## Measurements and interpretation

The copied runner retains the original 208-process plan: 160 object-return runs,
24 serialization runs, and 24 size-scaling runs. It alternates baseline/candidate
ordering, runs one process at a time, pins the chosen CPU, and imposes a 120-second
watchdog on each owned process group. Each process runs a separate first batch,
three warmups, and seven measured batches. The probe checks exact full results,
code points, and serialization outside timing. Paired witnesses must agree.

Every input forces `skip_json_loads=True` to measure the heuristic repair path.
This is why the candidate preserves #1003 and #1004 while changing only the repair
accumulator. Results do not establish a CPython, PyPy, or GraalPy ranking, and they
are not a complete alpha.4 release evaluation.

The runner checkpoints raw records after every completed process. Inspect
`completion.json`: a partial run or a failed validation is not a completed campaign.
`summary.json` and `summary.md` distinguish ratios of process medians from median
paired ratios. Raw stdout/stderr, complete command environments, source hashes,
binary hashes, CPU/toolchain metadata, and memory observations remain beside them.
JIT startup and process RSS have broader scope than warmed batch timings.

`runner-provenance.json` records the original harness hash and the portable copy's
hash. The copy changes only root/toolchain/CPU configuration and corresponding CPU
description/error text. It does not change workloads, counts, ordering, checks,
timing, or summary calculations.

## Validation of this reproduction bundle

The scripts were inspected and syntax-checked only (`ast.parse` for Python and
`bash -n` for the shell wrapper). This bundle was prepared while the original
campaign ran; it was not executed, cloned, rebuilt, or timed in that session.
The original source/native correctness evidence is separate from this portable
reproduction recipe. A fresh invocation must pass its own tree/hash/build checks.
