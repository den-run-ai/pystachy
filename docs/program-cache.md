# Native program cache

The Linux native CLI reuses complete programs by default across `pystachy run` launches.
A valid hit skips parsing, inference, LLVM optimization and machine-code
generation. The program still starts afresh: imports, definitions, input reads,
output and other effects run on every launch.

## Use it

Build the native compiler, then run a program normally:

```sh
./pystachy run example.py argument
./pystachy run example.py another-argument
```

The second launch can reuse the executable even when arguments, stdin or the
program's ordinary environment change. Add `PYSTACHY_PROGRAM_CACHE_TRACE=1` to
print `miss`, `frontend`, `stored`, `hit` or a bypass reason to stderr. Leave the
trace unset for ordinary execution. `PYSTACHY_PROGRAM_CACHE=0` disables the
program cache. Unset, empty and `1` enable it where supported.

The cache supports **Linux, a native compiler invoked by its path, the standard
Clang/GNU linker toolchain, and the default ORC JIT configuration**. It bypasses the cache for hosted compilation,
MCJIT, custom C flags or build environments, compiler diagnostics, CPython
embedding and external native libraries. `build`, `ext`, `ir`, `check` and `rt`
retain their existing behavior. Unsupported or uninspectable toolchain layouts,
custom Clang configuration files and undeclared shell wrappers also bypass it.

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
| Default native toolchain | Hash consumed C headers, shared libraries and GNU linker's CRT/library/script inputs. Snapshot existing and absent header, GCC, linker, loader and Clang configuration search candidates. |
| Compilation choices | Include source spelling, working directory, import paths, CPU features, optimization and inlining settings. |
| Additional generated/tool inputs | Declare files with the colon-separated `PYSTACHY_PROGRAM_CACHE_INPUTS` setting. Generated Python modules already participate as source inputs. |

Conflicting reads during inference retries, or changed dependencies before
publication, prevent publication. Static timestamps must have settled before a
memoized hash can be reused. A same-size edit with its mtime restored still
changes ctime; source checks independently read the contents.

The checked toolchain identity also keys the runtime object. A changed header or
search candidate cannot create a new program entry backed by an older runtime.
Large static files use the optional `/usr/bin/sha256sum` fast path; an unavailable
helper falls back to the bounded in-process hash. Source contents are always read.

Only a private cache owned by the current user is accepted. Manifests and
executables are checksummed, and complete artifacts are published before their
manifests using atomic renames. Missing, incomplete, corrupt or unusable entries
fall back to compilation. Hashes detect accidental damage; this is not a shared
cache or a defense against someone who can modify the user's compiler and files.

## Storage and concurrent launches

Artifacts live in `program-v2` under `PYSTACHY_CACHE` (the checkout default is
`build/`). Retention is limited to **256 program contexts and 256 MiB** of
executables plus manifests. Publication evicts the least recently used inactive
entries and removes superseded executables. The static hash memo has a separate
8 MiB bound. In-flight builds can temporarily require additional staging space.

Kernel locks deduplicate concurrent compilation of the same context. There are
256 permanent lock buckets; unrelated contexts occasionally share a bucket.
Waiting is limited to 30 seconds, then the waiting command compiles normally.
A killed compiler releases its lock automatically. Later accesses reclaim its
incomplete staging, while eviction skips active entries. Each launch executes
the program independently after opening its validated executable.

The cache is local and private. Tool wrappers must declare all additional inputs
with `PYSTACHY_PROGRAM_CACHE_INPUTS`; the compiler cannot infer arbitrary wrapper
behavior. Cross-user and remote caches are outside this contract.

To clear the cache, first stop Pystachy commands using it, then remove its subtree:

```sh
rm -rf "${PYSTACHY_CACHE:-build}/program-v2"
```

Do not remove lock files while commands are running. The runtime cache is
separate. Installed launchers normally choose a user cache
directory; set `PYSTACHY_CACHE` explicitly when inspecting or cleaning it.

## Validate and measure

```sh
make test-program-cache
python3 tools/program_cache_probe.py --compiler ./pystachy \
  --llvm "$PYSTACHY_LLVM" --benchmark-only --rounds 5 \
  --output build/program-cache-times.json
```

The correctness probe leaves the enable setting unset and checks skipped
frontend/LLVM work, invalidation, effects, failure recovery and concurrent
launches. CI runs it in the existing cache job; manifest, lifecycle, hashing and
toolchain unit tests also run in Lint. The benchmark
checks output before reporting uncached launches, cold program entries, hits and
prebuilt AOT execution. Cold program samples retain the warmed runtime/tool
metadata; first-use toolchain hashing is a separate cost. There are no timing
thresholds in CI. First fills add executable construction and input discovery;
cache validation also costs time. Report those costs separately from hits and
prebuilt AOT execution. Existing compiler/JIT benchmark runners explicitly disable
this cache to keep their compilation measurements comparable.
