# The runtime in the Pystachy subset

Pystachy's runtime has two parts: `runtime.py`, written in the same typed Python
subset as programs, and `runtime.c`, which provides memory management and native
services. Both JIT and AOT use them together.

The subset runtime is part of the normal build. The
[original evaluation](archive/runtime-prototype.md) records the earlier prototype,
its measurements and the decisions behind the split.

<a id="writing-the-runtime-in-the-subset"></a>
<a id="summary"></a>
<a id="1-the-prototype"></a>
<a id="16-what-moved-and-what-stays-in-c"></a>
<a id="17-how-much-more-could-move"></a>
## Responsibilities

| Part | Responsibilities |
|---|---|
| `runtime.py` | String methods, integer `math` functions, `fsum`/`prod`, dict hashing and format-spec parsing. |
| `runtime.c` | Collector, object and container memory layouts, I/O, signals, native library calls and float conversion. |
| `pystachy.py` | Runtime compilation, checked primitives, runtime signatures and linking. |

Moving a function into the subset keeps its C symbol and signature. Programs
continue calling the same runtime entry points. LLVM can inline across the two
parts after their bitcode is linked.

<a id="11-runtimepy-and-runtime-mode"></a>
<a id="12-the-primitives"></a>
<a id="13-calling-c"></a>
## Writing runtime code

Runtime mode exposes exported `pys_*` functions, declarations for C runtime
functions and a private `_rt` module for checked byte access, string construction
and explicit wrapping arithmetic. Ordinary programs cannot import `_rt`.

```sh
./pystachy rt runtime.py -o build/runtime.ll
```

The file remains valid Python. CPython substitutes test implementations of `_rt`,
so its algorithms can be tested independently of the compiler. Runtime mode
rejects module initialization, globals and classes; exported signatures must agree
with the runtime ABI. See the [runtime reference](reference/runtime.md) for the
exact rules and the string-builder lifetime contract.

<a id="14-building-caching-and-the-bootstrap"></a>
<a id="23-compilation-and-bootstrap"></a>
<a id="244-build-cost-and-size"></a>
## Building and caching

The driver compiles `runtime.py`, compiles `runtime.c` with clang, links their
bitcode and optimizes the combined module. It caches that bitcode and the object
used by JIT execution. The cache accounts for source and compiler changes, C
flags, disabled optimizations and the LLVM tools.

The self-hosting bootstrap checks that compiler stages emit identical runtime IR.
The Python-free verification stage rebuilds the runtime with the native compiler.
Cache details and exclusions are in the [reference](reference/runtime.md#build-and-cache).

<a id="15-testing-on-cpython-rtcheck"></a>
<a id="2-evaluation"></a>
<a id="21-robustness"></a>
<a id="22-quality-and-testability"></a>
<a id="24-performance"></a>
<a id="241-workloads"></a>
<a id="242-the-moved-functions"></a>
<a id="243-what-the-primitives-are-worth"></a>
<a id="25-scalability"></a>
<a id="26-extensibility"></a>
<a id="27-code-reuse"></a>
<a id="28-the-typed-ir"></a>
<a id="29-the-ongoing-bug-fixes"></a>
<a id="210-what-an-adversarial-review-found"></a>
<a id="211-on-the-typed-ir-the-measurements-again"></a>
## Verification

`make verify` combines compiled differential tests with independent CPython
checks of `runtime.py`. The runtime checks cover signatures, effects and recursion
through runtime calls. The bootstrap also compares its generated IR.

```sh
python3 tools/rtcheck.py
make test-cache
make verify
```

Subset arithmetic and primitive accesses have checks, but compiler lowering is
still part of the trusted implementation. C sanitizers instrument `runtime.c`;
they do not automatically instrument the emitted code of `runtime.py`.
See [testing](testing.md) for the full workflow.

<a id="3-how-other-compilers-and-runtimes-do-it"></a>
<a id="4-risks-and-how-the-prototype-handles-them"></a>
<a id="5-recommendation-and-next-steps"></a>
<a id="6-alternatives-considered"></a>
<a id="appendix-a-what-the-prototype-changes"></a>
<a id="appendix-b-reproducing-the-measurements"></a>
## Design history and future work

The [archived evaluation](archive/runtime-prototype.md) preserves benchmark
baselines, runtime inventories, alternative designs and migration proposals.
Those results compare specific historical revisions; current workload results
belong in [performance](performance.md).

A WebAssembly GC backend and further runtime migration remain design directions.
The `_rt` primitives were chosen to make another backend feasible; today's
execution path lowers to LLVM and uses the native runtime.
