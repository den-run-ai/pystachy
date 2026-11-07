# Cython and native CPython comparison builds

These optional builds compare the miniui example using the **same scalar C
adapter**, selected at process launch through `LD_LIBRARY_PATH`. They are
benchmark comparators, not additional supported UI packages. The original
`miniui.py`, `raylib_backend.py` and `benchmark_workload.py` remain unchanged.

## Variants

| Build directory | Widget core and workload | Backend | Purpose |
| --- | --- | --- | --- |
| `same_source` | Original `.py` compiled by Cython; regular Python classes | Original `.py` compiled by Cython, still using the CPython `ffi.extern` twin | Isolate compilation of identical source without redesigning its interface |
| `cpython_native` | Original `.py` executed by CPython | Original Python `Window` body, calling a compiled `miniui_native` extension | Conventional CPython native binding baseline, avoiding the generic FFI twin's per-call binding and `ctypes` overhead |
| `cython_native` | Original `.py` compiled by Cython; regular Python classes | Original `Window` body compiled with typed direct C helpers | Cython with a conventional native binding while retaining the class/container structure |
| `cython_typed` | Generated extension classes with declared fields and `cpdef` methods; selected typed locals; double unboxing of particle-list reads | Generated extension `Window`, typed command/rectangle locals and direct C helpers | Explicitly adapted Cython comparator with static layouts and C-level method calls |
| `same_source_auto` | Same source as `same_source`, with Cython's default safe type inference | Same original generic FFI backend | Standard-inference identical-source comparison; separate output preserves the inference-disabled diagnostic |
| `cython_native_auto` | Same source as `cython_native`, with Cython's default safe type inference | Same direct C binding and ordinary Python classes | Standard-inference conventional-binding comparison |
| `cython_typed_noexcept` | Same generated static-layout core and workload as `cython_typed` | Thirteen non-raising scalar helpers explicitly declared `noexcept` | Isolate implicit exception-check overhead without changing containers or algorithms |

`cpython_native` uses Cython to generate a normal CPython C extension. Its widget
and application loops execute in CPython; its renderer calls the extension once
per scalar operation. In `cython_native`, calls made inside the compiled backend
bind directly to C helpers; the separate workload's standalone `ffi` loop still
imports the exported Python method. `cython_typed` uses `cimport` for that loop,
so its `ffi` case is a direct compiled C call.

The typed comparator is **not identical-source compilation**. `typed_codegen.py`
parses the originals, rewrites class/method declarations and selected local
variable types, removes Python assignment annotations, and emits `.pyx`/`.pxd`
files. It preserves the algorithm and control flow, including the fused
simulation/drawing loop. Particle positions and draw commands remain Python
lists; each updated position is stored as a boxed Python float. It does not
introduce NumPy, C arrays, vectorization, batching, or a different simulation.
This is an explicit useful Cython optimization level, not a claim of maximum
attainable Cython performance.

## Build

The measured environment used CPython 3.13.16, Cython 3.1.8, setuptools 80.9.0 and
Clang 18.1.3. Install the build-only Python dependencies in an isolated location,
using the CPython interpreter that will load the extensions:

```sh
uv pip install --python /path/to/python3.13 \
    --target examples/miniui/bench_cython/deps \
    'Cython==3.1.8' 'setuptools==80.9.0'

PYTHONPATH=examples/miniui/bench_cython/deps /path/to/python3.13 \
    examples/miniui/bench_cython/build.py \
    --output build/miniui-bench-cython \
    --library-dir build/miniui-bench/adapters/stub \
    --cc /path/to/clang
```

The adapter must already exist. `--mode` builds one variant; `--without-workload`
is available for isolated wrapper compilation. Dependencies and generated
products are not required in source control. The generated shared objects do
not require Cython to be installed at runtime. `--mode all` builds only the
original four variants in the table; the three supplemental modes require an
explicit selection.

Every extension uses `-O3` without fast-math. Bounds checks, wraparound semantics,
initialization checks and the GIL are retained. The typed variant also enables
Cython's integer overflow checks. Cython automatic type inference is disabled
except in the two `_auto` variants, which use the default safe inference
setting. A `build-metadata.json`
records interpreter/compiler versions, source digests, options and exact
transformation label. Regenerate all variants after changing the shared
workload; compare its recorded SHA-256 before timing.

`infer_types=False` is an explicit conservative setting, **not Cython's
default**. Cython 3.1.8 defaults to `infer_types=None`, which uses safe inference
for suitable local values. Inference-disabled identical-source results should
be labelled accordingly. The static-layout variants provide a separate
explicitly typed comparison. Use `same_source_auto` and `cython_native_auto`
when reporting unchanged-source behavior with the default inference setting;
retain the inference-disabled variants as diagnostics. The supplemental modes
change no other compiler directives or source transformation. Metadata records
both the `infer_types` value and a readable `inference` policy for each new build.

The native extension links to `libminiui.so` without an embedded RPATH and uses
`-Wl,-z,now`. Changing `LD_LIBRARY_PATH` selects the same stub, verification, or
real raylib library for all native bindings. It does not statically link a
special faster adapter. Benchmark-only `benchmark_control` functions remain on
the shared FFI path and execute outside the measured interval.

## Run and validate

Run from the repository root with the variant directory **first** on
`PYTHONPATH`. Use `python -c` so the entry script's directory cannot accidentally
shadow the extensions with the original `.py` files:

```sh
PYTHONPATH=build/miniui-bench-cython/cython_typed:examples/miniui:tools/rt_cpython \
LD_LIBRARY_PATH=build/miniui-bench/adapters/verify \
/path/to/python3.13 -c \
 'from benchmark_workload import run; run("frame", 150, 7, 2)'
```

`check.py` is a short correctness check for the verifying adapter, separate from
statistical measurement:

```sh
/path/to/python3.13 examples/miniui/bench_cython/check.py \
    --output build/miniui-bench-cython \
    --library-dir build/miniui-bench/adapters/verify \
    --record examples/miniui/bench_cython/validation.json
```

It checks module import paths, the ten existing headless UI scenarios, native
API error handling, and state/drawing-operation parity for all six workload
modes at 150 and 2,000 particles. Elapsed times are deliberately excluded from
its comparisons. Performance measurement should start only after the shared
harness verifies all variants and all builds have finished.

## Optional scalar exception-check sensitivity

`cython_typed_noexcept` is a separate, opt-in comparison against `cython_typed`.
It changes only the exception declarations of thirteen C scalar forwarding
helpers: `_close`, `_open`, `_focused`, `_mouse_x`, `_mouse_y`, `_mouse`, `_keys`,
`_character`, `_dt`, `_begin`, `_end`, `_clip`, and `_rect`. These helpers forward
already-typed arguments to the C adapter without Python operations. Declaring
them `noexcept` removes the implicit Python exception-state checks at their
compiled call sites.

The string helpers `_init`, `_text`, `_width` and `checked_utf8` retain exception
propagation. All Python-exported integer/range validation remains in place, as
do exceptions from widgets, allocation, containers and checked arithmetic.
`infer_types=False` and every other compiler directive remain the same, so this
comparison isolates scalar-call exception overhead.

Build the optional variant after other measurements have stopped:

```sh
PYTHONPATH=examples/miniui/bench_cython/deps /path/to/python3.13 \
    examples/miniui/bench_cython/build.py \
    --output build/miniui-bench-cython \
    --library-dir build/miniui-bench/adapters/stub \
    --cc /path/to/clang \
    --mode cython_typed_noexcept

/path/to/python3.13 examples/miniui/bench_cython/check.py \
    --output build/miniui-bench-cython \
    --library-dir build/miniui-bench/adapters/verify \
    --modes cython_typed cython_typed_noexcept
```

The checker also compares generated `.pyx`/`.pxd` sources with the original
typed build, when present, to ensure that only these exception declarations
changed. Metadata lists the changed helpers, the transformed binding digest,
and the baseline variant. Keep this bounded sensitivity result separate from
the primary measurements; it is not a new algorithm or container rewrite.

The `same_source_auto` and `cython_native_auto` modes provide separate output
directories with only `infer_types` changed to `None`. Build them with
the same command using the corresponding `--mode`, then include them in the
checker with `--modes same_source_auto cython_native_auto cython_typed_noexcept`.
The checker verifies source identity with the original modes when present,
as well as the default inference setting. Their measurements must be recorded
separately from the original inference-disabled results.

## Type and error boundaries

Packed RGBA values cross the native boundary as `unsigned int`, including values
above `INT_MAX`. Python-exported extension methods explicitly reject noninteger
coordinate/color arguments because Cython's default integer argument converter
would otherwise truncate floats. They check signed/unsigned C ranges, reject
embedded NUL in text, retain UTF-8 encoded bytes throughout each C call, and
propagate exceptions. Strings use UTF-8 with `surrogatepass`, matching the
existing CPython FFI twin. Error messages and exception classes can differ from
the twin: for example, `ctypes` wraps its noninteger conversion `TypeError` in
`ctypes.ArgumentError`, while the native export raises `TypeError` directly.
The invalid-input checks establish rejection, while state and rendering
equivalence apply to the benchmark's valid input domain.

The typed comparator assumes the benchmark's documented, valid scalar domain:
coordinates and dimensions fit the adapter's signed 32-bit API, colors fit
unsigned 32-bit, and integer simulation/layout bookkeeping fits signed 64-bit.
Its typed fields/methods restrict the broader dynamic behavior of ordinary
Python classes. It is not a general drop-in replacement for arbitrary objects,
dynamic attributes, or arbitrary-precision integer inputs. Compiled internal
calls use C types; Python export checks are relevant to the Python-callable API.
