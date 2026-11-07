# Native benchmark adapters

These builds compile the production `../raylib_adapter.c` unchanged. Each emits
`libminiui.so`; select a build with `LD_LIBRARY_PATH` so every language mode uses
the identical native library within a comparison.

```sh
python3 examples/miniui/bench_native/build_native.py --out build/miniui-bench/adapters
```

The default real build uses `pkg-config raylib` and requires raylib 5.5 or newer.
`--raylib-dir /path/to/raylib/src` selects a directory containing `raylib.h` and
`libraylib.so` directly. `--cc` selects the compiler, and `--stub-only` skips the
real build. The output manifest records compiler, flags and source/binary hashes.

| Build | Purpose | Instrumentation |
| --- | --- | --- |
| `stub` | Time Python/native submission without a renderer | Every drawing operation increments counters; no argument hashing |
| `verify` | Untimed equality checks on C operations and arguments | Same counters plus a deterministic 32-bit digest |
| `real` | Real raylib rendering and screenshots | Unmodified raylib calls; unavailable counters return `-1` |

The stub supplies no input and no frame delay. Its text measurement is a synthetic
ASCII width (`strlen(text) * size / 2`), so it is a submission benchmark, not a
model of real font layout or GPU cost. The verification digest includes operation
order, integer arguments, packed colors and text bytes. It is a mismatch detector,
not a collision-free proof. Digest values fit signed 64-bit FFI results.

The counters observe raylib calls beneath the scalar adapter. In particular,
`miniui_begin` contributes two calls (`BeginDrawing`, `ClearBackground`), and
`miniui_end` contributes two when a clip is active (`EndScissorMode`, `EndDrawing`).
They therefore differ from scalar FFI call counts. `clips` counts
`BeginScissorMode` calls, `rects`/`texts` count primitives, and `widths` counts
`MeasureText` calls. Benchmark control reads are excluded from counters.

`../benchmark_control.py` declares the common helper ABI. After creating a
`Window`, call `configure()` to set target FPS to zero and clear the VSync flag
on the real backend. Call `reset()` before an untimed verification pass. The
real `snapshot(path)` captures and exports the framebuffer; run it outside the
measured interval. Stub snapshots return zero and produce no file.

No input override, offscreen substitute renderer, or production code change is
used for the real build. Hardware/display limitations of a particular run must
be recorded with its benchmark results.
