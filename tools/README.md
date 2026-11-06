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
| Check retained CPU-buffer failure paths | [check_cpu_buffers.sh](check_cpu_buffers.sh) | Linux CPython-buffer metadata, bounds and allocation cleanup; optional sanitizers and a missing-release negative control. See [the prototype](../bench/cpu_buffers/README.md). |
| Measure standard-library import coverage | [import_sweep.py](import_sweep.py) | Actual compilation of one import per module; import success does not establish API behavior. |
| Refresh the top-PyPI inventory | [pypi_inventory.py](pypi_inventory.py) | Resolve ranked releases, scan pinned wheels and replay the same stdlib dependencies against two compiler builds ([method](../tests/upstream/pypi/inventory.md)). |
| Grow the CPython-derived corpus | [cpython_test_methods.py](cpython_test_methods.py) | Which unittest methods of a `Lib/test` file pass natively once their scaffolding is rewritten by fixed rules, and one program of the passing ones; record its output with `tests/record.sh` ([guide](../tests/upstream/core-sweep.md#mechanical-method-extraction-2026-11-02)). |
| Verify declared upstream port coverage | `make port-check` | Pinned sources, adaptation diffs and upstream tests of selected ports under CPython. Compiled behavior needs the differential suite separately. |
| Find performance changes | [perf_smoke.py](perf_smoke.py), `make bench-extended` | Checked workload outputs and separate compilation/execution measurements. See [performance](../docs/performance.md) and [kernel controls](../bench/smoke/README.md). |
| Inspect emitted LLVM | [ir_cost_report.py](ir_cost_report.py) | Static call sites, runtime declarations/definitions and input hashes; static counts do not measure runtime cost. |
| Inspect typed stages or a compiler diagnostic | [inspect_compiler.py](inspect_compiler.py) | Same-run typed snapshots, pass diffs and structured diagnostics in the [hosted inspection prototype](../docs/compiler-inspection.md). |
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

The metadata-only [submission check](check_submission.py) enforces the
[issue/PR format](../CONTRIBUTING.md#issues-and-pull-requests) without running PR
code. Its format/API controls run in Lint (`test_submission.py`).

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
