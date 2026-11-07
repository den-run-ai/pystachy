# Optional text kernels

This prototype compares two independent compile-time switches against the current
runtime. Neither switch is enabled by default.

* `PYSTACHY_STRINGZILLA` redirects the existing JSON byte-scan predicate (quote,
  backslash, or byte below 32) when at least 128 bytes remain. Other predicates
  and short spans keep the current portable word scan. The caller's UTF-8
  decoding and Python code-point/error positions are unchanged.
* `PYSTACHY_FLOAT_SPAN` retains the existing ASCII/Unicode numeric conversion and
  lexical checks. It passes an already terminated, validated numeric span to
  locale-isolated libc `strtod`; a trimmed trailing boundary gets one bounded
  copy, and underscores are filtered into one reserved buffer. It checks the
  returned end pointer against the exact logical end. This is a libc experiment;
  it does **not** integrate or measure `fast_float`.

Refs [#30](https://github.com/den-run-ai/pystachy/issues/30) and
[#655](https://github.com/den-run-ai/pystachy/issues/655). The default implementation
and compiler behavior remain the control. This prototype is intended for a draft
research PR; focused tests and measurements do not establish the full release gate.

## Dependency and deployment

The adapter uses actual StringZilla **5.3.2**, pinned to the commit resolved by its
release tag, [`3cd0f9bcab97912dd36ca4ca4253f1f46b33ef8e`](https://github.com/ashvardanian/StringZilla/tree/3cd0f9bcab97912dd36ca4ca4253f1f46b33ef8e).
The upstream [bounded character-set API](https://github.com/ashvardanian/StringZilla/blob/3cd0f9bcab97912dd36ca4ca4253f1f46b33ef8e/include/stringzilla/find.h)
returns a pointer to the first matching byte or null. The
[Haswell implementation](https://github.com/ashvardanian/StringZilla/blob/3cd0f9bcab97912dd36ca4ca4253f1f46b33ef8e/include/stringzilla/find/haswell.h)
is selected only after checking AVX2, BMI, BMI2 and LZCNT. The same adapter falls
back to upstream's serial routine when these features are absent; only the
reported backend was measured. The executable keeps an AOT model.

The adapter is built into a separate shared library because Pystachy's driver
removes LLVM target attributes from runtime helpers before inlining. Keeping SIMD
functions outside that module preserves their target requirements. This also
means the optional executable has a shared-library deployment dependency; binary
size results must include `libtextkernels.so`. This prototype runner targets Linux
with clang/LLVM 18. It has not validated macOS, Windows, other CPUs or static linking.

No upstream source is copied into this repository. The runner extracts pristine
headers, `VERSION` and the complete upstream
[Apache 2.0 license](https://github.com/ashvardanian/StringZilla/blob/3cd0f9bcab97912dd36ca4ca4253f1f46b33ef8e/LICENSE)
from the pinned Git object, retaining source comments and attribution. Redistribute
that license with the optional adapter. Source files and the adapter are hashed.
Each run gets a new private output directory and fresh runtime caches. This is
necessary because `PYSTACHY_CFLAGS` is a cache input but arbitrary external header
contents are not. Do not replace an adapter/header in place beneath an existing
runtime cache.

## Reproduce

Use the repository's pinned CPython and supported LLVM toolchain, and build the
compiler using `make` first. The runner accepts an existing StringZilla clone; its
working tree is ignored in favor of the exact commit.

```sh
git clone --depth 1 --branch v5.3.2 https://github.com/ashvardanian/StringZilla.git /tmp/stringzilla
flock build/text-kernels.lock python3 bench/text_kernels/run.py \
  --compiler ./pystachy --stringzilla-source /tmp/stringzilla \
  --output build/text-kernels-run --cpu 0 --repeats 5
```

Choose a CPU present in the process's allowed affinity mask. The output directory
must not exist and must contain no whitespace. A run preserves `results.json`,
all executed commands, compiler/probe binaries, probe output and dependency
snapshots. Use `--checks-only` to omit timings. No performance threshold is a test.
Do not run other heavy work concurrently.

The four variants are baseline, float only, StringZilla only, and combined. The
runner first compares exact stdout and empty stderr against pinned CPython in
native AOT, JIT and stressed AOT. C probes compare scan positions with an independent
scalar loop, cover short and long spans at different alignments, and put protected
pages directly after the readable span. They exercise allocation/copy counters
without timing those instrumented builds. Float parser counters count bytes
submitted to parser copies, including NUL; they exclude any Unicode normalization
and internal buffer-growth recopy in the control. A probe-only `GC_RAW_REQUEST`
hook counts actual raw-allocation requests and their requested bytes during the
ASCII parser call; allocator size-class rounding and GC pacing credits are not
reported as allocated bytes. Input construction is outside these counters.

Timing uses existing complete JSON decoding and repair-facade workloads from
[`../extended/json_scan.py`](../extended/json_scan.py), including short, long,
Unicode, sparse escapes and dense escapes. Every returned value/checksum is
validated before and after timing. Numeric workloads split a comma-separated
batch, parse every token and compute a weighted score. Their independently known
binary-exact results cover short, plain, long, trimmed, underscored and Unicode
numbers. The runner compares every non-clock output field with CPython before
accepting any timing, rotates variant order, and pins one CPU. Startup, cold
runtime creation, warmed AOT builds and dependency build costs are separate from
internal steady-state timers.

### Instruction-count replay and dispatch check

After a full run, replay its exact native binaries under Callgrind. The replay
checks binary, adapter and workload hashes before accepting any count, and checks
every non-clock output against CPython. It includes the whole process and is not
a wall-clock benchmark. Valgrind is an optional analysis dependency.

```sh
flock build/text-kernels.lock python3 bench/text_kernels/count_instructions.py \
  --results build/text-kernels-run/results.json \
  --output build/text-kernels-instructions --valgrind valgrind
clang -O2 -Wall -Wextra -Werror tools/text_kernels/backend_probe.c \
  -L"$PWD/build/text-kernels-run" -ltextkernels \
  -Wl,-rpath,"$PWD/build/text-kernels-run" -o build/text-kernels-backend
build/text-kernels-backend
valgrind --tool=callgrind --callgrind-out-file=build/text-kernels-backend.callgrind \
  build/text-kernels-backend
```

The backend probe must report the selected implementation both natively and under
Callgrind. Valgrind can expose a different CPU feature set; interpret instruction
counts using its reported backend, not just the native one.

### Independent review reproductions

The compact deterministic generator retains the exact 2,281 inputs used in the
independent float review, including invalid syntax, Unicode, very long input,
exception messages, signed zero and signed NaN. This example replays the optional
AOT path against the pinned CPython oracle; the main runner already checks the
committed regression fixtures in all four variants and three execution modes.

```sh
python3 tools/text_kernels/generate_float_review.py build/float-review.py
python3 build/float-review.py > build/float-review-cpython.out
PYSTACHY_HOME="$PWD" PYSTACHY_CACHE="$PWD/build/float-review-cache" \
  PYSTACHY_CFLAGS=-DPYSTACHY_FLOAT_SPAN \
  ./pystachy build build/float-review.py -o build/float-review
build/float-review > build/float-review-native.out
cmp build/float-review-cpython.out build/float-review-native.out
python3 tools/text_kernels/check_adapter_bounds.py \
  --library build/text-kernels-run/libtextkernels.so \
  --output build/text-kernels-adapter-bounds.json
```

The last helper calls the exact shared object across 36,787 protected-page cases
and records its backend/hash. A GCC build of the same adapter selects the serial
implementation on x86-64 and can be checked with the same helper.

See [results](results/README.md) for measured outcomes and limitations.
