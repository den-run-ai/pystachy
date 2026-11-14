# Native compiler PGO experiment

Optional Linux x86-64 experiment for LLVM IR profile-guided optimization of the
native compiler. The [recorded results](results/2026-11-10.json) use compiler source
`04860a83618e744c6f461761b6ee7fdbbe21f985`, Linux x86-64, LLVM 19.1.7,
CPython 3.13.16. They are historical measurements, not timings of subsequent
harness safeguards or tests. Production build defaults and compiler/runtime
sources are unchanged.

## Method and provenance

[Serc's PGO methodology](https://github.com/astral-experiments/serc/blob/b57c94f27ebd181238f59e8db1f1b010f4c9635c/docs/development.md),
particularly its ordinary-output oracle and separate training/measurement inputs,
inspired this experiment. The runner and its tests are original project code
under Pystachy's [MIT license](../../LICENSE), independently implemented using
LLVM's documented IR profiling flags. No Serc implementation, corpus, fixture
or dependency is copied.
Training and holdout sources already belong to this checkout and keep their
existing licenses and notices. The local Debian toolchain is not redistributed.

The ordinary bootstrap uses an unmodified `make`, including three-stage compiler
and runtime fixed points. A temporary transparent Clang launcher captures the
actual linked, pre-optimization compiler bitcode from a subsequent ordinary
self-build. In the recorded experiment, that control executable was byte-identical
to `make`'s executable.
All variants use those same bitcode bytes and the driver's normal sequence:

1. Clang `-O2` to bitcode, with `-fprofile-generate` or `-fprofile-use` only here.
2. The existing two `forceattrs` passes and late allocator inlining.
3. Clang code generation with LLVM optimization passes disabled.
4. Native linking; only the instrumented executable links the profiling runtime.

Generic `PYSTACHY_CFLAGS` injection is intentionally avoided: those flags also
reach the separately compiled C runtime and later code-generation steps.

Training uses self-compilation, runtime compilation, generic functions,
recursive generics and nested cleanup. JSON repair, the JSON codec, byte BPE,
microgpt and n-body are held out from profile generation. This means their entry
programs are held out; libraries and compiler paths can overlap with training.
The merged profile contains 2,296 functions. Nonzero counters were verified in
lexer, parser, inference and lowering functions. A high-level wrapper can be
inlined before instrumentation, so requiring that one symbol would be invalid.

The manifest pins source files, input bytes, linked bitcode, binary/profile
hashes, tool executables, their loaded shared libraries and the profile runtime.
It records every command, diagnostic, return code, duration and peak RSS.
Profile warnings, source drift, artifact drift or missing correctness evidence
stop the experiment. Each requested artifact must be freshly produced and
nonempty; a failed re-verification invalidates its earlier success marker.
Output comparisons precede both time and memory measurements. Fast gate tests
run through `make check-fast` and need no LLVM installation or compiler build.

## Correctness evidence

- Ordinary bootstrap: compiler stages 1/2/3 identical, **892,614 IR lines**;
  runtime stages 1/2/3 identical, **21,100 lines**.
- Ordinary, instrumented and PGO output equality on the training inputs; PGO
  output equality on all five held-out programs and both fixed-point outputs.
  The PGO candidate was not used for a separate three-stage bootstrap.
- Full existing corpus: **4,395/4,395** identical IR/diagnostic/exit outcomes:
  **2,505** accepted with identical nonempty IR and **1,890** identical rejections.
  A separate audit of all 8,790 native invocations found no crash, timeout,
  internal compiler error, missing output, source drift or binary drift.

The recorded result also retains counts from separate local semantic and syntax
pilots. Their tools are outside this prototype and the reproduction commands
below. The separate full-corpus invocation audit is likewise historical evidence;
the existing `tools/irsame.sh` command below reproduces corpus parity.

This is local prototype validation, not the full release matrix. Alternate
architectures, LLVM releases, GC-stress compiler runs and sanitizer configurations
have not been established by this experiment.

## Measured result

Eight alternating warm samples per variant, pinned to CPU 0 on an AMD EPYC 9V74
host. All other experiment builds/tests were stopped during this cohort. Shared
host noise remains possible. These are process-start-inclusive frontend times.

| Input | Role | Ordinary | PGO | Less time |
|---|---|---:|---:|---:|
| Compiler self-compilation to IR | Training | 3.94 s | 3.47 s | 11.9% |
| Runtime compilation to IR | Training | 52.3 ms | 46.4 ms | 11.3% |
| JSON repair | Held out | 246 ms | 217 ms | 11.8% |
| Byte BPE | Held out | 147 ms | 132 ms | 10.2% |
| microgpt | Held out | 30.0 ms | 27.2 ms | 9.3% |
| JSON codec | Held out | 27.1 ms | 25.3 ms | 6.4% |
| n-body | Held out | 5.23 ms | 4.98 ms | 4.8% |

Self and JSON repair improved in all eight paired observations; BPE improved in
seven. The n-body difference is only 0.25 ms and should carry little weight in a
decision. The executable shrank from **6,416,648 to 6,037,848 bytes (5.9%)**.

This supports an optional compiler optimization experiment. It does not establish
a 12% whole-bootstrap improvement: external LLVM optimization/code generation
is unchanged and takes most of a native self-build. Generated program throughput
is not what this benchmark measures.

The initial `wait4` memory readings included the Python harness's pre-exec RSS
floor on small jobs. They are retained as raw observations and must not be treated
as actual small-program compiler memory. The separate GNU `time` memory phase
measures the native child after the meter has executed, avoiding that floor.
Those separate single observations were **849.5 MiB ordinary / 835.1 MiB PGO**
for self-compilation and **57.2 / 57.0 MiB** for held-out JSON repair. They are
descriptive memory checks, not a repeated memory benchmark or a promised gain.
The committed result file retains both the original raw readings and the
correctly metered follow-up.

## Reproduce

Use Linux x86-64, the project-pinned CPython, a complete matching LLVM toolchain
with its profiling runtime, and GNU `time` for the memory phase. The runner also
uses `ldd` and `taskset`. LLVM 19.1.7 is the tested version. Set `LD_LIBRARY_PATH`
if using a locally extracted toolchain. Start from ordinary Makefile defaults,
use a fresh output directory and keep compiler/runtime sources unchanged.

```sh
export PYSTACHY_LLVM=/absolute/path/to/llvm/bin
make PY=python3.13
for phase in capture instrument train optimize verify; do
  python3.13 bench/compiler_pgo/prototype.py "$phase" \
    --llvm "$PYSTACHY_LLVM" --output build/compiler-pgo
done
PYSTACHY_HOME="$PWD" PYSTACHY_JOBS=2 tools/irsame.sh \
  build/compiler-pgo/ordinary build/compiler-pgo/pgo
python3.13 bench/compiler_pgo/prototype.py measure \
  --llvm "$PYSTACHY_LLVM" --output build/compiler-pgo --samples 8
python3.13 bench/compiler_pgo/prototype.py memory \
  --llvm "$PYSTACHY_LLVM" --output build/compiler-pgo --time-tool /usr/bin/time
```

Run each step only after the preceding one succeeds. Both binaries deliberately
use this checkout's `PYSTACHY_HOME`: the comparison changes only native compiler
optimization and keeps source/runtime inputs identical. The runner defaults to
the lowest permitted CPU; use `--cpu` to select another permitted core.
Timings include process startup and frontend compilation to `/dev/null`, after
warmup, with eight
alternating samples per variant pinned to one CPU. They do not measure generated
program execution or the external LLVM backend. Do not benchmark alongside
other builds or test suites.

## References

- [Serc PGO methodology](https://github.com/astral-experiments/serc/blob/b57c94f27ebd181238f59e8db1f1b010f4c9635c/docs/development.md)
- [LLVM instrumentation-based profiling](https://clang.llvm.org/docs/UsersManual.html#profiling-with-instrumentation)
