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
| Run adapted pytest tests natively | [pytest_native.py](pytest_native.py) | Static collection, generated typed fixtures/tests and independent original-pytest phase comparison; see the [bounded source contract](../docs/pytest-native.md). |
| Check shared example and benchmark assertions | [pytest_native_suites.py](pytest_native_suites.py) | Explicit independent suites with isolated imports, original pytest comparison and complete case execution; `make test-pytest-workloads` runs JIT/AOT. |
| Qualify original upstream test methods | [pytest_native_upstream.py](pytest_native_upstream.py), [pytest_native_json_repair.py](pytest_native_json_repair.py) | Original unittest/pytest cases, exact source and case inventories, adapted pytest, generated CPython and native JIT/AOT must agree. See [upstream selections](../tests/upstream/pytest/README.md). |
| Prove test failures remain failures | [pytest_native_controls.py](pytest_native_controls.py) | Independent seeded success/failure inventory for assertions, aliases, Unicode, numbers, exceptions, fixture cleanup and strict XPASS. Included in `make test-pytest-native`. |
| Verify compiler and runtime changes | `make verify` | The complete verification plan, including bootstrap, native execution and configuration variants. `tests/verify.sh --list` lists its groups. |
| Check the temporary bootstrap tier | `python3 tools/check_bootstrap_tier.py build/ci-bootstrap` | Force an O1 temporary/O2 final Make bootstrap and compare all witnesses with a same-checkout verified O2 bundle; preserves the bundle and records diagnostic timings. Use an exclusive checkout. |
| Compare a program with CPython | `make test FILES="tests/programs/AREA/CASE.py"` | JIT/AOT output and status agree with the recorded CPython reference. Use `make test-py` for the hosted compiler. |
| Compare compiler revisions | `make irsame REF=<base-sha>` | Corpus LLVM, diagnostics and exit status, with each compiler's own library/runtime inputs. |
| Check runtime declarations and ABI | `make check-runtime` | Runtime signatures, effects, implementation inventory and recursion through runtime calls. The verification plan also runs native ABI probes. |
| Check retained CPU-buffer failure paths | [check_cpu_buffers.sh](check_cpu_buffers.sh) | Linux CPython-buffer metadata, bounds and allocation cleanup; optional sanitizers and a missing-release negative control. See [the prototype](../bench/cpu_buffers/README.md). |
| Adapt CPU DLPack batches | [pystachy_dlpack.py](pystachy_dlpack.py) | Optional NumPy bridge to retained read-only float64 buffers; [native scoring and lifetime checks](../examples/cpu_dlpack/README.md). |
| Run local executable batches | [application_workers.py](application_workers.py) | Optional CPython coordinator with at most two workers, declared resource admission, deadlines and process-group cleanup. See [local application workers](#local-application-workers). |
| Measure standard-library import coverage | [import_sweep.py](import_sweep.py) | Actual compilation of one import per module; import success does not establish API behavior. |
| Refresh the top-PyPI inventory | [pypi_inventory.py](pypi_inventory.py) | Resolve ranked releases, scan pinned wheels and replay the same stdlib dependencies against two compiler builds ([method](../tests/upstream/pypi/inventory.md)). |
| Grow the CPython-derived corpus | [cpython_test_methods.py](cpython_test_methods.py) | Extract/triage unittest methods, combine passing methods for `tests/record.sh`, or export an explicitly selected pytest suite with source hashes and an exclusion manifest ([corpus guide](../tests/upstream/core-sweep.md#mechanical-method-extraction-2026-11-02), [pytest bridge](../docs/pytest-native.md)). |
| Verify declared upstream port coverage | `make port-check` | Pinned sources, adaptation diffs and upstream tests of selected ports under CPython. Compiled behavior needs the differential suite separately. |
| Fuzz the json_repair port against upstream | [json_repair_fuzz.py](json_repair_fuzz.py) | Deterministic malformed inputs, with or without a generated JSON Schema, replayed through pristine upstream under CPython, the port under CPython and its native build: typed values, text, logs and errors must be equal. Not run by CI; see the [replay corpus](../tests/upstream/json_repair/README.md#differential-fuzz). |
| Fuzz the json_repair port's schema validator | [json_repair_validator_fuzz.py](json_repair_validator_fuzz.py) | Generated schemas and instances through `jsonschema` and the port's validator under CPython: error classes and messages must be equal. Needs `jsonschema`; CI runs [its recorded answers](../tests/upstream/json_repair/README.md#schema-guided-repair). |
| Refresh JSON repair and schema timings | [json_repair_refresh.py](json_repair_refresh.py), [json_repair_bench.py](json_repair_bench.py) | Pinned upstream, native and CPython-companion configurations with complete-result checks and source/binary fingerprints; see the [benchmark guide](../bench/json_repair/README.md). |
| Find performance changes | [perf_smoke.py](perf_smoke.py), `make bench-extended` | Checked workload outputs and separate compilation/execution measurements. See [performance](../docs/performance.md) and [kernel controls](../bench/smoke/README.md). |
| Check JIT launch descriptors and signals | `make jitprobe`, [jitfdprobe.py](jitfdprobe.py) | Inherited pipes survive ordinary, `-O0` (`llc`), embedding and cached launches; descriptor tables (also a child's), closed standard streams, inherited SIGINT dispositions, runtime variants and cleanup agree with CPython. |
| Check complete-program reuse | `make test-program-cache`, [program_cache_probe.py](program_cache_probe.py) | Native cache invalidation, fresh execution effects and skipped work; optional complete-launch measurements ([guide](../docs/program-cache.md)). |
| Inspect emitted LLVM | [ir_cost_report.py](ir_cost_report.py) | Static call sites, runtime declarations/definitions and input hashes; static counts do not measure runtime cost. |
| Check reduced LLVM optimizations | [llvm_validation.py](llvm_validation.py) | [Extracted scalar kernels](../docs/llvm-validation.md), structural verification, finite CPython/native agreement, optional llubi path checks and Alive2 refinement. |
| Inspect typed stages or a compiler diagnostic | [inspect_compiler.py](inspect_compiler.py) | Same-run typed snapshots, pass diffs and structured diagnostics in the [hosted inspection prototype](../docs/compiler-inspection.md). |
| Check a dynamic payload's guard | [check_lean_boundary.py](check_lean_boundary.py), `make check-lean-boundary` | A [Lean prototype](lean_boundary/README.md) checks tag guards in a supported fragment of one exported function, or every function of a snapshot (`--all`); its IR normalization and runtime correspondence remain unproved. |
| Prove every dynamic payload read and unchecked access of the test corpus | [check_lean_corpus.py](check_lean_corpus.py), `make check-lean-corpus` | Compiles each dynamic-`Any` test program with the hosted compiler and requires Lean to accept every function that reads a payload or has an unchecked list read or dict entry. |
| Check unchecked list reads and dict entries | [check_lean_access.py](check_lean_access.py), `make check-lean-boundary` | A [Lean prototype](lean_boundary/ACCESS.md) proves each `list.load` index within its list's length and each dict or set entry it reads or writes live, in every function of a snapshot; its IR normalization and runtime contracts remain unproved. |
| Check release/install tooling | `make test-install`, [release_smoke.py](release_smoke.py), [release_notes.py](release_notes.py) | Installation unit tests, release-artifact checks and release-note checks and rendering described in the [release guide](../docs/releasing.md); release publication has additional gates. |

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

## Local application workers

`application_workers.py` runs explicit argument arrays from a JSON manifest.
Use it for independent local executable jobs. Replace the executable below
with an absolute path and place the input files beside `jobs.json`:

```json
{"version": 1, "jobs": [
  {"key": "first", "argv": ["/absolute/path/to/program"],
   "memory_bytes": 134217728, "input_bytes": 4096, "stdin": "first.txt"},
  {"key": "second", "argv": ["/absolute/path/to/program"],
   "memory_bytes": 134217728, "input_bytes": 4096, "stdin": "second.txt"}
]}
```

```sh
python3 tools/application_workers.py jobs.json --report results.json \
  --jobs 2 --cpus 2 --memory-mib 256 --input-mib 1 --timeout 60
```

The defaults allow one worker and one reserved CPU, a 60-second deadline per
job, 1 GiB of estimated memory, 64 MiB of active/queued input, and 1 MiB of
combined stdout/stderr per job. `--jobs` and `--cpus` cannot exceed two;
`--timeout` must be finite, positive and at most 900 seconds. The output limit
must remain positive. Output sizes are polled, so a fast writer can exceed the
limit before cancellation; cleanup reads and captured prefixes remain bounded.
Deadlines run from supervisor launch until the coordinator observes completion
of the whole job tree; delayed observation fails closed. Startup waits continue
checking existing jobs' deadlines and output limits. Each startup handshake is
also bounded by the smaller of the job deadline and five seconds.

Each job reserves `cpu` (default one), `memory_bytes` and `input_bytes` (default
zero) for its whole child tree. Memory is an admission estimate, not an enforced
RSS limit. Keep inputs stable while jobs run and include all their bytes in the
reservation; the tool checks the size of `stdin` files. Input and `cwd` paths
are relative to the manifest, with its directory as the default working
directory. An optional `env` object adds string environment values. Standard
BLAS/OpenMP thread settings are capped to the job's CPU reservation; other
programs must honor that reservation themselves. The manifest is limited to
1 MiB and 10,000 jobs; the scheduler prefetches only one waiting descriptor.

Run the Linux coordinator in its own main thread, with no pre-existing children
and the default SIGCHLD handler. Each job starts a small CPython supervisor in
the same process group; children must remain in that group and must not daemonize.
The supervisor adopts orphaned descendants and keeps the job's reservations,
deadline and output limit active until every descendant has been reaped. Leader
exit alone never releases resources or finalizes output.

On an observed failure, timeout, output overflow or signal, the coordinator stops
queued work. Cleanup repeatedly terminates and reaps children until the kernel
confirms none remain, including children forked during shutdown. If a supervisor
dies, the coordinator adopts and cleans its children and reports failure. Caller
signal handlers and the previous subreaper setting are restored afterward.
The report retains submission order,
exit status, output sizes/hashes, bounded text and timing; `complete` is false
on failure. Reports cannot replace the manifest, declared stdin files or
executables. They are published atomically in an existing parent directory.

The reusable lifecycle is in [process_workers.py](process_workers.py). Its
scope belongs in a dedicated coordinator's main thread; the CLI supplies its
resource budget and rejects failed results before resuming queued work.
The supervisor in [process_worker_child.py](process_worker_child.py) adds one
small CPython process per admitted job; CPU measurements include its overhead.
`python3 -m unittest discover -s tools -p 'test_process_worker*.py'` checks
admission, output limits, report publication, launch races and descendant
cleanup without LLVM. Other operating systems are rejected before work starts.

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
