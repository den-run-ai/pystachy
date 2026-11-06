# Native program cache prototype

The opt-in cache reuses a complete native program across `pystachy run` launches.
A valid hit skips parsing, inference, LLVM optimization and machine-code
generation. The program still starts afresh: imports, definitions, input reads,
output and other effects run on every launch.

## Try it

Build the native compiler, then enable the cache for a command:

```sh
PYSTACHY_PROGRAM_CACHE=1 ./pystachy run example.py argument
PYSTACHY_PROGRAM_CACHE=1 ./pystachy run example.py another-argument
```

The second launch can reuse the executable even when arguments, stdin or the
program's ordinary environment change. Add `PYSTACHY_PROGRAM_CACHE_TRACE=1` to
print `miss`, `frontend`, `stored`, `hit` or a bypass reason to stderr. Leave the
trace unset for ordinary execution. Setting `PYSTACHY_PROGRAM_CACHE=0`, or
leaving it unset, keeps the existing execution path.

This prototype supports **Linux, a native compiler invoked by its path, and the
default ORC JIT configuration**. It bypasses the cache for hosted compilation,
MCJIT, custom C flags or build environments, compiler diagnostics, CPython
embedding and external native libraries. `build`, `ext`, `ir`, `check` and `rt`
retain their existing behavior.

## What is reused

A miss runs the ordinary JIT IR passes, then compiles their output to machine
code with further LLVM IR passes disabled. It links that object with the normal
JIT runtime object. This keeps the JIT's inlining and allocation decisions;
ordinary AOT builds use a separate whole-program optimization pipeline.

The final executable is cached. Hits do not load bitcode into `lli`. Linking also
preserves native constructor execution, which cannot be assumed when handing an
object alone to `lli`. Program arguments, standard streams, status, signals and
`PYSTACHY_GC_STRESS_PROGRAM` are applied to each fresh execution.

## Invalidation

| Input | Check |
|---|---|
| Main program and imported Python files | Hash the text actually consumed, and reread it on every hit. Size and mtime alone never validate source. |
| Import resolution | Replay positive and negative file/package/namespace probes, including resolved paths. A new shadowing module invalidates the entry. |
| Compiler, runtime and LLVM | Record resolved files, content hashes and size/mtime/ctime snapshots. Settled unchanged static files can reuse their hashes. |
| Default native toolchain | Record consumed C headers, LLVM shared libraries and GNU linker's opened CRT/library/script inputs. |
| Compilation choices | Include source spelling, working directory, import paths, CPU features, optimization and inlining settings. |
| Additional generated/tool inputs | Declare files with the colon-separated `PYSTACHY_PROGRAM_CACHE_INPUTS` setting. Generated Python modules already participate as source inputs. |

Conflicting reads during inference retries, or changed dependencies before
publication, prevent publication. Static timestamps must have settled before a
memoized hash can be reused. A same-size edit with its mtime restored still
changes ctime; source checks independently read the contents.

Only a private cache owned by the current user is accepted. Manifests and
executables are checksummed, and complete artifacts are published before their
manifests using atomic renames. Missing, incomplete, corrupt or unusable entries
fall back to compilation. Hashes detect accidental damage; this is not a shared
cache or a defense against someone who can modify the user's compiler and files.

## Limits and cleanup

The prototype records consumed default toolchain inputs, but does not establish
a hermetic SDK or arbitrary tool-wrapper contract. Keep the toolchain's search
layout fixed: adding a new higher-priority header or linker input is outside the
recorded-file checks. Tool wrappers must declare their underlying inputs. Remote
caches, cross-host reuse, eviction and deduplicating simultaneous misses remain
follow-ups to [#104](https://github.com/den-run-ai/pystachy/issues/104).

Artifacts live in `program-v1` under `PYSTACHY_CACHE` (the checkout default is
`build/`). Each process uses private staging; concurrent misses can compile the
same program independently. Interrupted staging directories and old executables
are ignored and retained until cleanup. To clear this prototype's artifacts:

```sh
rm -rf "${PYSTACHY_CACHE:-build}/program-v1"
```

The runtime cache is separate. Installed launchers normally choose a user cache
directory; set `PYSTACHY_CACHE` explicitly when inspecting or cleaning it.

## Validate and measure

```sh
make test-program-cache
python3 tools/program_cache_probe.py --compiler ./pystachy \
  --llvm "$PYSTACHY_LLVM" --benchmark-only --rounds 5 \
  --output build/program-cache-times.json
```

The correctness probe checks skipped frontend/LLVM work, invalidation, effects,
failure recovery and concurrent launches. CI runs it in the existing cache job;
the manifest and dependency-parser unit tests also run in Lint. The benchmark
checks output before reporting uncached launches, cold program entries, hits and
prebuilt AOT execution. Cold program samples retain the warmed runtime/tool
metadata; first-use toolchain hashing is a separate cost. There are no timing
thresholds in CI.
