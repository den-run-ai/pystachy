# Retained CPU-buffer scoring prototype

This experiment adds one retained consumer of an existing CPython numeric batch:
`Object.buffer_f64()` plus `Buffer.dot()`. The implementation and its CPython twin
are in [`lib/pyobj.py`](../../lib/pyobj.py),
[`pyembed.c`](../../pyembed.c), and
[`tools/rt_cpython/pyobj.py`](../../tools/rt_cpython/pyobj.py). The
[API contract](../../docs/ffi.md#retained-cpu-buffer-prototype) specifies layout,
permissions, lifetime, arithmetic and concurrency.

The host creates two `array.array('d')` objects. The compiled
[`cb`](../../tests/ffi/ext/cb.py) extension acquires them in `retain()`, scores them
in separate `score()` calls, and releases them in `release()`. Native code keeps
reading the original allocation after the source `Object` is closed or the host
drops its own array reference. This is groundwork for later DLPack and numerical
kernels; neither DLPack nor arbitrary NumPy/PyTorch package support is implemented.

## Reproduce

Use the repository's pinned Python and LLVM setup, with the development virtual
environment on `PATH`. `make` builds the compiler; the benchmark accepts that
native binary and builds its own extension.

```sh
make
out=$(mktemp -d)
python3 bench/cpu_buffers/bench.py "$out" --compiler ./pystachy \
  --samples 9 --output "$out/results.json"
```

The optional `--cpu N` chooses a permitted CPU. Otherwise the benchmark selects
one available CPU and pins its process there on Linux. `--compiler` measures one
build with a new empty runtime/glue cache and another reusing that cache; the
result records both times and the resulting artifact sizes. Without `--compiler`,
pass a directory containing an already built `cb.abi3.so` and `cbdata.py`; build
metadata is then `null`.

The benchmark records compiler and extension SHA-256, LLVM version, build
configuration, Python version, host CPU, source hashes, all timing samples,
preparation time, logical copy bytes, and element-extraction counts.

## Workload and controls

Every path starts with the same finite, exactly representable host values and
returns the same scalar score. Array creation and the sequential Python reference
are outside timed regions. Each timed region includes complete calls from CPython
into the compiled extension. Before timing, each path is checked; the final result
of every timed batch is also checked for exact equality and finiteness. A NaN
cannot pass through a tolerance comparison. Variant order rotates across nine
samples. The small-input cases include the zero-length call floor.

| Path | Per scoring call |
|---|---|
| `retained` | Read two retained buffers with the native dot kernel. |
| `open_each_call` | Look up and acquire the data buffer, run the same dot kernel against retained weights, then close it. |
| `copy_each_call` | Copy the data array, acquire the copy, run the same dot kernel against retained weights, then close it. |
| `boxed_elements` | Look up both arrays and extract two Python float objects per element through `pyobj`; accumulate in compiled code. Limited to 1,024 elements. |

The copy control copies only changing data, keeping weights retained as an
application with fixed model weights would. Its host copy helper counts `8 * n`
payload bytes per call; the other paths account for zero payload copies. The
boxing count describes `2 * n` element-extraction API operations, not total
allocations, GC time or bytes; metadata, wrappers and return values still
allocate.

All bulk paths use the same scalar sequential binary64 kernel with floating-point
contraction disabled, so this experiment isolates data access and ownership
costs, not alternative numerical kernels.

## Results

The committed [Linux x86-64 measurements](results/linux-x86_64.json) use base
`f7103067545b43cdcd8ce20dc66b1571425b3a8d` and record exact source hashes. The
source-identical, verified baseline native compiler is reused with this checkout's
library and rebuilt C embedding glue. The toolchain was Ubuntu clang version
18.1.3 (1ubuntu1), CPython 3.13.16, on an AMD EPYC 9V74 80-Core Processor
(CPU 0). The default driver used `-O2`, without extra C flags or disabled
Pystachy optimizations. The benchmark environment is one shared container, so
these are local prototype measurements, not release thresholds.

| Elements | Retained | Open per call | Copy per call | Boxed elements |
|---:|---:|---:|---:|---:|
| 0 | 0.102 µs | 0.629 µs | 1.589 µs | 0.656 µs |
| 8 | 0.094 µs | 0.564 µs | 1.380 µs | 10.686 µs |
| 1,024 | 6.287 µs | 6.560 µs | 8.000 µs | 453.125 µs |
| 65,536 | 318.549 µs | 321.229 µs | 357.958 µs | — |
| 1,048,576 | 4,961.861 µs | 5,036.374 µs | 7,133.841 µs | — |

For 1,048,576 elements, retaining the batch avoids 8 MiB of payload copying per
score and takes 4.962 ms versus 7.134 ms for the copy control (1.44×
copy/retained, 2172 µs difference). Both keep 16 MiB of input/weight exports alive
during the session. Reopening an existing buffer is much closer at this size;
the sequential dot dominates. The small-batch paths show acquisition and Python
element-access overhead more clearly.

The [earlier nine-sample run](results/linux-x86_64-earlier.json), before the final
private metadata-helper refactor, measured 2.255 ms retained versus 2.945 ms with
copying at 1,048,576 elements (1.31×). Its original source hashes are preserved.
The refactor produced a **byte-identical extension**: both reports record SHA-256
`9cd978ef6201afbf28e7677a96aa6ecda62068e0da956fe1df24271ba0891b67`.
The final run above is the primary result; the spread between runs shows that
absolute timings on this shared host are sensitive to host conditions, and the
1.31× and 1.44× copy/retained ratios are not a stable release guarantee.

The full extension, containing all four paths, is 163,616 bytes. One empty-cache
build took 20.680 s and one build reusing the runtime/glue cache took 5.275 s;
these single build observations were pinned to the same CPU as the benchmark.
These whole-extension figures are not an estimate of this feature's incremental
binary or compilation cost.

## Ownership and verification

A root capsule owns one CPython `Py_buffer` export. Each derived view retains the
root capsule. Every data operation holds the GIL; the numerical loop releases
neither the GIL nor control to Python. The last release calls `PyBuffer_Release`
once. The importer accepts only direct, contiguous, one-dimensional native `d`
exports; checked derived views can have positive or negative strides. A read-only
handle rejects writes even when the exporter is writable. Host aliases can still
change values between calls. External writers that do not hold the GIL require
caller synchronization.

The native fixture checks sliced and deliberately unaligned memoryviews, nested
reverse views, signed arithmetic extremes, writable aliases, rejected layouts,
closed handles and unequal lengths. PEP 688 callbacks verify release counts,
resizing fails while the export is live, and allocation pressure collects 200
dropped retained buffers. Numerical cases include cancellation, an FMA-sensitive
input, NaN, infinity, overflow and signed zero. The extension client verifies
retention across calls and host reference drops, owner-thread rejection, explicit
release and repeated sessions.

```sh
make test-ffi
PY=python3.13 CC=clang tools/check_cpu_buffers.sh
PY=python3.13 CC=clang tools/check_cpu_buffers.sh --negative-control
ASAN_OPTIONS=detect_leaks=0 PY=python3.13 CC=clang \
  tools/check_cpu_buffers.sh '-fsanitize=address,undefined -fno-omit-frame-pointer'
```

The isolated C probe requires Linux and CPython development headers. It calls the
actual embedding helpers with 15 malformed exporters, checks empty/null payload
handling and extreme derived-view arithmetic, and injects four allocation failures
(root descriptor, root capsule, view descriptor, view capsule). Its negative
control removes `PyBuffer_Release` from a temporary source copy and requires the
release-count assertion to fail. ASan/UBSan exercise those C paths; leak detection
is disabled because this harness links a prebuilt, unsanitized CPython. Exporter
release/refcount assertions remain active.

Local validation with the pinned CPython 3.13.16 and LLVM 18.1.3 passed:

- CPython twin versus native JIT and AOT with program GC stress set to `1`;
  compiled extension client parity with GC stress, alias mutation, resize pinning,
  retained lifetime and explicit release; five private API/constructor diagnostics.
- The isolated malformed-export/arithmetic/allocation-failure probe, its deliberate
  missing-release negative control, and the probe under ASan plus UBSan.
- Full FFI suite: 159 passed, 0 failed; its JSON-repair comparison reported
  645/645 matches. This full run preceded the final movement of an internal
  metadata helper from a class method to a private module function; the focused
  JIT/AOT, extension, diagnostic and sanitizer checks above were rerun afterward.
- `make lint check-recordings check-repository`: 2,142 recordings, 122 documented
  deviations and 11 library files checked, zero failures; 67 runtime pointer stores,
  zero root problems; all 11 repository-hygiene unit tests passed.
- The committed benchmark rebuilt the extension from the final implementation;
  all preflight and timed-batch result/copy-counter checks passed.

The full `make verify` matrix, the full GC groups, and other operating systems or
architectures were not run locally. This research prototype is submitted as a
draft; required CI and review remain prerequisites for any promotion.

This prototype has no multidimensional imports, foreign/device-memory ownership,
async completion, shared-memory IPC, exporter-side DLPack or Arrow support. The
root export's span is tracked for pressure, not as physical memory accounting,
and is capped at 1 GiB per handle; multiple views overcount shared storage.
Acquisition uses `PyBUF_FULL_RO` like `memoryview`; writable permission is
checked from the returned export rather than requested through `PyBUF_WRITABLE`.
