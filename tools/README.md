# Development tools

Run these commands from the repository root. Follow the
[development setup](../docs/install.md#python-and-development-tools-with-uv)
for the pinned Python and LLVM versions; `tools/setup.sh --check` checks the
basic build prerequisites. The [testing guide](../docs/testing.md) describes
which checks each kind of change needs.

## Choose a tool by task

| Task | Entry point | What it establishes |
|---|---|---|
| Check source hygiene and compiler unit tests | `make check-fast` | Python lint/type checks, repository hygiene and selected fast compiler tests. |
| Verify compiler and runtime changes | `make verify` | The complete verification plan, including bootstrap, native execution and configuration variants. `tests/verify.sh --list` lists its groups. |
| Compare a program with CPython | `make test FILES="tests/programs/AREA/CASE.py"` | JIT/AOT output and status agree with the recorded CPython reference. Use `make test-py` for the hosted compiler. |
| Compare compiler revisions | `make irsame REF=<base-sha>` | Corpus LLVM, diagnostics and exit status, with each compiler's own library/runtime inputs. |
| Check runtime declarations and ABI | `make check-runtime` | Runtime signatures, effects, implementation inventory and recursion through runtime calls. The verification plan also runs native ABI probes. |
| Measure standard-library import coverage | [import_sweep.py](import_sweep.py) | Actual compilation of one import per module; import success does not establish API behavior. |
| Verify declared upstream port coverage | `make port-check` | Pinned sources, adaptation diffs and upstream tests of selected ports under CPython. Compiled behavior needs the differential suite separately. |
| Find performance changes | [perf_smoke.py](perf_smoke.py), `make bench-extended` | Checked workload outputs and separate compilation/execution measurements. See [performance](../docs/performance.md) and [kernel controls](../bench/smoke/README.md). |
| Inspect emitted LLVM | [ir_cost_report.py](ir_cost_report.py) | Static call sites, runtime declarations/definitions and input hashes; static counts do not measure runtime cost. |
| Check release/install tooling | `make test-install`, [release_smoke.py](release_smoke.py) | Installation unit tests and release-artifact checks described in the [release guide](../docs/releasing.md); release publication has additional gates. |

For an import survey, use the CPython source directory for your installation:

```sh
python3 tools/import_sweep.py -j 2 --metadata build/import-sweep-meta.json \
  ./pystachy /usr/lib/python3.13 build/import-sweep.json
```

The sweep excludes modules already provided by Pystachy's library and records
first errors. Source-feature counts and historical port-edit categories are not
compatibility tests: compile and execute the API your application uses. See
[measuring coverage](../docs/stdlib.md#measuring-coverage) for overlays, diagnostic
stubs and the limits of each measurement.

## Focused checks and measurements

The remaining tools support narrower contracts: runtime allocation/GC probes,
regex bounds and parity, JSON parity, dynamic `Any` and promoting-integer
acceptance, compiler-state ownership, and library-port checks. Their docstrings
and the corresponding Makefile targets describe inputs and scope. Many manual
tools remain useful even when they are not part of the default CI matrix.

Keep benchmark drivers beside their reproduction instructions. The runtime
microbenchmarks in [rtbench/](rtbench/) compare two compiler revisions using
[rtbench.py](rtbench.py); regex, textwrap and cache drivers are documented in
[caching](../docs/caching.md). Run correctness checks before comparing timings,
and record the compiler revision, toolchain, workload and configuration.

Add reusable checks here and register their tests in the appropriate CI target.
Keep one-off evaluation output outside the source tree. Remove tools whose model
no longer matches the compiler, update their callers and documentation together,
and retain the old implementation in Git history.
