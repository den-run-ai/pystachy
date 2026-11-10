# Local native compiler wheel pilot

This pilot records a 2026-11-10 packaging experiment at compiler commit
`04860a83618e744c6f461761b6ee7fdbbe21f985`. It packages the ordinary verified
native compiler, without PGO, beside the existing hosted implementation.
No Serc implementation or fixture was imported. Its distribution idea motivated
this independently written pilot; [idea provenance](#idea-provenance) is recorded below.

The installed launcher chooses a bundled `native/pystachy` when present.
`PYSTACHY_COMPILER=hosted` forces the Python compiler;
`PYSTACHY_COMPILER=native` requires the native payload; unset or `auto` selects
it if available. Ordinary source wheels retain their hosted fallback. Native
and hosted paths use the same installed runtime and library resources and the
existing LLVM provisioning code. LLVM is still an external requirement.

## Observed benefit

On this Linux x86_64 host, native dispatch reduced frontend latency by 81–85%.
The complete JSON AOT build improved by 11%, because the LLVM backend and linker
still perform their normal work.

| Installed CLI workload | Hosted median | Native median | Reduction | Speedup |
|---|---:|---:|---:|---:|
| Compiler self IR | 26.799 s | 3.940 s | 85.3% | 6.80x |
| BPE tokenizer IR | 1.197 s | 0.174 s | 85.4% | 6.87x |
| JSON codec IR | 0.250 s | 0.046 s | 81.5% | 5.42x |
| JSON codec complete AOT build | 2.599 s | 2.307 s | 11.3% | 1.13x |

These are four alternating samples per backend, after one warmup each, pinned
to CPU 0. Each sample starts the installed CLI from outside the checkout and
includes Python launcher startup. Both modes use the same installed wheel.
Page and runtime caches are warm; the `ir` command excludes LLVM optimization,
machine-code generation and linking. `build` includes those stages. These are
local observations, not CI performance thresholds or a multi-platform claim.

Maximum process RSS is measured by a small GNU time subprocess, avoiding the
inherited RSS floor of a large Python measurement parent. It is the maximum
individual process RSS observed by that invocation, not simultaneous summed
process-tree memory.

| Workload | Hosted median maximum RSS | Native median maximum RSS |
|---|---:|---:|
| Compiler self IR | 727.93 MiB | 849.00 MiB |
| BPE tokenizer IR | 65.62 MiB | 66.14 MiB |
| JSON codec IR | 26.87 MiB | 22.29 MiB |
| JSON codec complete AOT build | 84.38 MiB | 84.66 MiB |

Native self-compilation used about 16.6% more peak memory. The wheel makes an
existing fast compiler reachable through pip; it does not improve its memory
behavior.

### Default program cache

The native Linux compiler's existing program cache is enabled by default;
hosted compilation bypasses it. The separate cache cohort used an independently
written deterministic JSON example and verified CPython stdout on every run.
Trace checks before and after the timed samples showed native `hit`; the hosted
trace showed `bypass native compiler path required`. `LD_LIBRARY_PATH` and
`PYSTACHY_PROGRAM_CACHE` were unset; no cache guards or tool wrappers were changed.

| JIT scenario | Hosted | Native |
|---|---:|---:|
| First launch with empty application/runtime caches, one observation | 16.875 s | 24.532 s |
| Warm launches, median of four alternating samples | 0.923 s | 0.178 s |
| Warm launches, median maximum process RSS | 41.31 MiB | 16.23 MiB |

The 5.19x warm-launch gain is specific to native cache hits versus hosted
recompilation, with startup included. First-use toolchain discovery and cache
publication have a cost: the observed native first launch was slower. The
single first-use observations have warm OS pages and fresh per-backend caches;
they are not repeated cold-machine benchmarks. Unsupported build environments
still bypass the cache, as documented in [program-cache.md](../../docs/program-cache.md).

## Correctness and artifact checks

The ordinary native compiler passed the repository's compiler stage1 == stage2
== stage3 fixed point and runtime fixed point before packaging. The builder
requires its exact binary hash and every recorded compiler/runtime input hash.
Package-only commits may descend from the compiler commit; the receipt records
the package and compiled-source revisions separately, along with launcher,
builder and source-wheel hashes and any tracked package diff.

`pilot.py` checks a clean source-wheel installation, automatic native selection,
and forced hosted/native execution from another directory. To prove dispatch,
it temporarily hides the installed Python compiler sources: native IR generation
still works, and forced hosted compilation fails. It restores the sources in
`finally`. Hosted and native IR files match byte for byte for self, JSON and
BPE. Both JIT and AOT execution match a CPython JSON oracle; complete JSON codec
AOT outputs match CPython after dropping the workload's printed elapsed-time
line. Workload, transitive self-compiler source and installed resource hashes
are checked before and after verification/measurement. Measurement refuses an
unverified or changed identity.

Twelve focused tests cover missing/broken/forced dispatch, argument and user
cache preservation, mismatched binary and compiler source bytes, failed fixed
points and unrelated package revisions. Existing release audit defaults and
release workflows are unchanged. The twelve focused tests run through the
existing `make check-fast` CI target. The optional local pilot commands add no
release or CI matrix jobs.

### ABI, licensing and size

The wheel tag is deliberately `py3-none-linux_x86_64`. The audited binary's
largest required GLIBC symbol version is 2.38; its dynamic dependencies are
`libc.so.6`, `libgcc_s.so.1` and `libm.so.6`, with the standard x86_64 loader and
no RPATH. This inspection is not a manylinux certification and does not change
the project's documented Linux release baseline. No other architecture or
operating system was packaged or installed in this experiment.

The measured source wheel is 1,885,412 bytes; the measured native wheel is
4,737,301 bytes; its uncompressed compiler is 6,416,648 bytes. Existing MIT,
`THIRD_PARTY_NOTICES` and Ryu Boost license files are checked and retained.
No Serc code, fixture or lockfile is bundled. LLVM and GNU time are external
tools, not wheel payloads. GNU time is used only for local measurement.

## Idea provenance

The distribution idea came from Serc at
`b57c94f27ebd181238f59e8db1f1b010f4c9635c`: its
[release documentation](https://github.com/astral-experiments/serc/blob/b57c94f27ebd181238f59e8db1f1b010f4c9635c/docs/releasing.md)
describes Python wheels containing the native executable, and its
[packaging configuration](https://github.com/astral-experiments/serc/blob/b57c94f27ebd181238f59e8db1f1b010f4c9635c/pyproject.toml)
uses Maturin's binary bindings. Serc offers
[MIT](https://github.com/astral-experiments/serc/blob/b57c94f27ebd181238f59e8db1f1b010f4c9635c/LICENSE-MIT)
or [Apache-2.0](https://github.com/astral-experiments/serc/blob/b57c94f27ebd181238f59e8db1f1b010f4c9635c/LICENSE-APACHE)
licensing. These links credit the design motivation; this pilot's launcher,
builder, tests and measurement scripts were independently written for Pystachy.
No Serc source, fixture, lockfile or documentation text is redistributed here.
The new implementation uses Pystachy's existing MIT license; existing third-party
notices remain in the package.

## Reproduce locally

Use pinned CPython 3.13.16, setuptools 84.2.1 and wheel 0.48.0. The measured
toolchain was Debian LLVM 19.1.7 on Linux x86_64, glibc 2.41. Build an ordinary
source wheel with the project's existing packaging first. Obtain a verified
ordinary native compiler and `manifest.json` from the
[companion PGO prototype](https://github.com/den-run-ai/pystachy/blob/codex/compiler-pgo-prototype/bench/compiler_pgo/README.md),
or supply equivalent recorded evidence with the same schema. The wheel uses
the ordinary baseline compiler, not the companion's PGO output. Its builder
requires the manifest's source revision and input hashes, bootstrap binary
hash, and successful `ordinary-compiler-fixed-point` check. The PGO runner is
not imported by the launcher, builder or tests, and is not required to install
or run either wheel. Both proposals can be reviewed against main independently.
When generating new evidence with a separate checkout of the companion runner,
pass its `--repo` option the wheel source checkout. The evidence revision must
be an ancestor of the package revision, with identical recorded compiler/runtime
inputs; a manifest from an unrelated PGO branch is deliberately rejected.
This tool never downloads or builds a compiler.

With `WHEEL_CHECKOUT` and `PGO_CHECKOUT` naming those two checkouts, the ordinary
compiler and required manifest can be prepared as follows. Only the companion's
`capture` phase is needed; PGO instrumentation, training and optimization are not
required for this wheel.

```sh
make -C "$WHEEL_CHECKOUT" PY=python3.13 PYSTACHY_LLVM="$LLVM"
python3.13 "$PGO_CHECKOUT/bench/compiler_pgo/prototype.py" capture \
  --repo "$WHEEL_CHECKOUT" --llvm "$LLVM" --output "$EVIDENCE/baseline"
VERIFIED_NATIVE_COMPILER="$WHEEL_CHECKOUT/pystachy"
BASELINE_MANIFEST="$EVIDENCE/baseline/manifest.json"
```

Then run the builder and installed-package checks from the wheel checkout:

```sh
python3.13 tools/build_native_compiler_wheel.py \
  --wheel "$SOURCE_WHEEL" \
  --native-binary "$VERIFIED_NATIVE_COMPILER" \
  --baseline-manifest "$BASELINE_MANIFEST" \
  --output "$EVIDENCE/native-dist"

python3.13 -m venv "$EVIDENCE/native-venv"
"$EVIDENCE/native-venv/bin/pip" install --no-index --no-deps "$NATIVE_WHEEL"
python3.13 -m venv "$EVIDENCE/source-venv"
"$EVIDENCE/source-venv/bin/pip" install --no-index --no-deps "$SOURCE_WHEEL"

for phase in smoke verify measure; do
  python3.13 bench/compiler_wheel/pilot.py "$phase" \
    --native-cli "$EVIDENCE/native-venv/bin/pystachy" \
    --source-cli "$EVIDENCE/source-venv/bin/pystachy" \
    --llvm "$LLVM" --time-command "$GNU_TIME" --output "$EVIDENCE/run"
done

python3.13 bench/compiler_wheel/cache_pilot.py \
  --native-cli "$EVIDENCE/native-venv/bin/pystachy" \
  --source-cli "$EVIDENCE/source-venv/bin/pystachy" \
  --llvm "$LLVM" --time-command "$GNU_TIME" --output "$EVIDENCE/cache-run"

PYTHONPATH=. python3.13 tools/test_native_compiler_wheel.py
```

Use a new output directory for each cache cohort. The script refuses to report
warm-cache gains without both the native-hit and hosted-bypass traces. Stop
other compiler builds and benchmark jobs while timing. The builder refuses to
overwrite an existing wheel and writes the exact input manifest beside it.

The experiment's raw run records, command lines, stdout/stderr, GNU time RSS,
sample arrays, artifact hashes and source provenance are under `wheel-evidence/`
outside the checkout. `run-v2` is the measured frontend/AOT cohort; `cache-run`
is the separate cache cohort. The initial `run` was smoke-only and is not used
for timing claims. Rebuilt artifacts after the local package commit must match
the measured executable, launcher and resources; metadata-only changes do not
require repeating the timing cohort.

[The compact evidence record](results/2026-11-10.json) preserves all measured
sample rows, correctness checks, exact IR hashes, cache traces, installed
identities and the final artifact's provenance. The wheel rebuilt from clean
packaging commit `14845bde99cc5873d47389414ddf5f3f39132011` contains all 170
measured payload/resource members byte-identically. Only its provenance receipt
and corresponding `RECORD` changed; its final size is 4,737,610 bytes.

Before release work, build on the project's supported platform baselines,
validate wheel tags and installed resources on each target, and deliberately
extend the release audit for any new artifact set. The current source-wheel
release path remains unchanged. During the recorded experiment, wheels were
built and installed locally; no package release was published.

This one-host pilot does not complete the platform and installation matrix in
[#998](https://github.com/den-run-ai/pystachy/issues/998). Read-only installations,
relocation, pip/uv installation and removal, and private-cache behavior across
supported targets still need release-level validation. The committed observations
remain measurements of the recorded payload; documentation and CI registration
changes do not add new timing claims.
