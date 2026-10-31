# The runtime in the Pystachy subset

Pystachy's runtime has two parts: `runtime.py`, written in the same typed Python
subset as programs, and `runtime.c`, which provides memory management and native
services. Both JIT and AOT use them together as part of the normal build.

This guide covers the architecture, development workflow and private interface
used by `runtime.py`. Ordinary programs cannot use that interface.

- [Responsibilities](#responsibilities) and [writing runtime code](#writing-runtime-code).
- [Runtime ABI](#runtime-mode-and-abi), [private primitives](#private-primitives) and [container storage](#list-and-dict-storage).
- [Build and cache](#build-and-cache), then [verification](#verification).

## Responsibilities

| Part | Responsibilities |
|---|---|
| `runtime.py` | String methods, integer `math` functions, `fsum`/`prod`, dict hashing and format-spec parsing. |
| `runtime.c` | Collector, object and container memory layouts, I/O, signals, native library calls and float conversion. |
| [The compiler](../src/README.md) | Runtime compilation, checked primitives, runtime signatures and linking. |

Moving a function into the subset keeps its C symbol and signature. Programs
continue calling the same runtime entry points. LLVM can inline across the two
parts after their bitcode is linked.

## Writing runtime code

Runtime mode exposes exported `pys_*` functions, declarations for C runtime
functions and a private `_rt` module for checked byte access, string construction
and explicit wrapping arithmetic. Ordinary programs cannot import `_rt`.

```sh
./pystachy rt runtime.py -o build/runtime.ll
```

The file remains valid Python. CPython substitutes test implementations of `_rt`,
so its algorithms can be tested independently of the compiler.

## Runtime mode and ABI

`./pystachy rt runtime.py` compiles runtime functions through the same typed IR as
programs, with these additional rules:

- Top-level `pys_*` definitions are exported under their C names. Every parameter
  must be annotated; `*args` is not allowed in exported signatures.
- `def pys_name(...) -> T: ...` declares a function provided by `runtime.c`.
  A `str` crosses this boundary as the runtime's `Str *`, rather than `char *`.
- Exported and external signatures cannot take or return `bool`: the runtime ABI
  passes booleans as `i64`, while a subset `bool` would lower to `i1`.
- Definitions and calls must agree with `RUNTIME` entries, including their logical
  types and layouts, rather than merely their LLVM types.
- Module scope permits functions, imports and docstrings. Module initialization,
  global variables, classes and computed parameter defaults are rejected. A
  parameter's default value must be a literal.
- A function cannot use an operation that lowers directly to itself. For example,
  `math.gcd()` inside `pys_m_gcd` would be recursive through lowering and is rejected.
  `tools/check_runtime.py` also checks cycles through `runtime.c`.

Programs supply their own entry point, roots and object callbacks. Runtime mode
does not emit replacements. `runtime.c` keeps prototypes for subset definitions
that its own functions call.

## Private primitives

`import _rt` is available only in runtime mode. Its implementations operate on
subset `str` and `int` values and emit LLVM instructions or calls recorded in the
runtime table.

| Primitive | Contract |
|---|---|
| `byte(s, i)` | Read byte `i`; raise `IndexError` outside `0 <= i < len(s)`. |
| `str_new(n)` | Allocate a zeroed buffer; `MemoryError` for negative sizes or sizes above `2**63 - 26` (the signed allocation limit minus the 24-byte string header and trailing NUL). |
| `str_put(s, i, c)` | Write at a checked index; `ValueError` unless `0 <= c <= 255`. |
| `copy(d, at, s, lo, n)` | `d[at:at+n] = s[lo:lo+n]` via `memmove`; `IndexError` for invalid ranges or negative `n`. |
| `str_done(s)` | Publish a buffer as an immutable string; emits no instruction. |
| `same(a, i, b, j, n)` | Compare via `memcmp`; `IndexError` for invalid ranges or negative `n`. |
| `find_byte(s, c, st, en)` | Search via `memchr`, returning an index or `-1`; check `0 <= st <= en <= len(s)` and `0 <= c <= 255`. |
| `find_sub(h, n, st, en)` | Search via `memmem`, returning an index or `-1`; check `0 <= st <= en <= len(h)`. |
| `null(s)` | Test the null pointer used for an omitted string argument. |
| `wrap_add`, `wrap_sub`, `wrap_mul` | Wrapping 64-bit arithmetic. |
| `shl(a, n)`, `lshr(a, n)` | Shift by `n % 64`; the right shift is logical. |
| `udiv(a, b)`, `urem(a, b)` | Unsigned division/remainder of 64-bit patterns; check zero. |
| `mul_ovf(a, b)` | Test whether signed multiplication would overflow. |

Two lifetime rules are manual:

1. Only `str_put` and `copy` may modify a buffer made by `str_new`, and only before
   `str_done`. Nothing checks that a string has not already been published.
2. An omitted string parameter, such as `strip()`'s characters, is a null pointer.
   Test it with `null` before reading its length or bytes. Dereferencing it crashes.

String length and byte accesses carry alias-analysis metadata so LLVM can retain
lengths and optimize construction loops. Runtime-mode unit-step range increments
use LLVM's signed no-overflow form; runtime authors must keep the loop valid for
that assumption.

## List and dict storage

List headers remain scanned so their backing arrays stay reachable. The backing of a
`list[int]`, `list[float]` or `list[bool]` is pointer-free (allocated atomic, never scanned):
`list(range(...))` makes one, and the compiler makes every other list of those types with
`pys_list_new_atomic`. That covers displays, comprehensions, `list()` of a tuple, and empty
lists whose type a later use decides, once it has decided it. The list layout and mutation
interface are unchanged.

Growth, copies, slices (stepped too), `+` and `*` allocate a new backing of the kind of the
backing they copy, which the page map records (`atomic_items`). A list that is emptied keeps
its kind in the sentinel it is left with. `list(d)` of a dict with int keys and `list(s)` of
an int set past its first 8 slots are pointer-free too. Slice assignment and deletion move
items within a list's backing. So a list keeps its kind for its lifetime: its type never
changes, since lists are invariant.

The one exception is an empty list that a template returns while its type is still open,
which each call's context types (`typed_empty`). It is allocated scanned, as are the copies
and growth made of it, because one allocation may serve a `list[int]` context and a
`list[str]` one. `tests/programs/runtime/gc_list_kinds.py` covers these cases under
`PYSTACHY_GC_STRESS_PROGRAM=1`, and `make listprobe` checks the allocation kinds directly.

Dict value arrays follow the same rule. The compiler makes a dict whose values are ints,
floats or bools with `pys_dict_new_atomic`, which sets the dict's `vatomic` word. Every value
array of that dict is then atomic, through growth and `clear()`, as are the value arrays of
its copies (`dict.copy()`, `dict(d)`) and `list(d.values())`. `dict.fromkeys` and an open
empty dict that a template returns are made scanned. Key arrays keep their own rule: those
of int keys are atomic. `tests/programs/runtime/gc_dict_values.py` and `make dictprobe` cover dict values.

<a id="building-and-caching"></a>
## Build and cache

The driver reads and compiles a source snapshot of `runtime.c`, its `ryu/` and `mpz/` includes
and `runtime.py`, links the bitcode with `llvm-link`, then runs `opt -O2`. The C
part is built with `-fexceptions` so exceptions can unwind through runtime frames.
When `PYSTACHY_CFLAGS` enables AddressSanitizer, generated subset definitions
are marked `sanitize_address` and compiled to bitcode through Clang's ASan
pipeline first. This supplies the selected target/layout and honors sanitizer
options without rerunning ASan on the already-instrumented C module. The subset's
ASan constructors use no COMDAT groups, so linking another sanitized C object
cannot discard a group that still has a renamed initializer referring to it.
Raw `rt` output and ordinary builds retain their existing IR.
On Linux, JIT normally loads a shared library built from the cached runtime object;
other platforms and failed or unavailable shared-library loads use the object path.
AOT links the runtime bitcode into the program. See the
[JIT/AOT pipeline](internals.md#jit-aot-and-runtime-caching) for the fallback rules.

Cache names have the form `build/runtime-py-<L>-<K>.bc`, `.o`, `.so` and `.target`;
the shared library is used on Linux.
The small `.target` file preserves the runtime's target triple and data layout;
JIT optimization applies them before folding object sizes and field offsets.
The content key
includes runtime and compiler bytes, C flags, disabled `PYSTACHY_OPT` passes and
LLVM tool identities. Host CPU information is included for flags such as
`-march=native`. The path/flag group `L` separates compiler and tool configurations.
When a new runtime is published, old entries in its group are removed.

`runtime-py.hashes` memoizes file hashes with size, mtime and ctime. Recently
modified files are hashed again to avoid coarse timestamp races. Builds use
private temporary files and publish complete artifacts by rename. If compiler or
tool inputs change during a build, its result is used privately rather than
published. Extension glue (`pyembed.c` and `pyext.c`) uses the same cache rules.

The key does **not** track tool shared libraries such as `libLLVM`, C headers or
clang configuration files. Clean the runtime cache when those change without a
corresponding tool change.

The self-hosting bootstrap checks that compiler stages emit identical runtime IR.
The Python-free verification stage rebuilds the runtime with the native compiler.

<a id="checks-and-test-boundaries"></a>
## Verification

| Check | Purpose |
|---|---|
| Runtime IR fixed point | Compiler stages agree on compilation of `runtime.py`. |
| `tools/check_runtime.py` | Runtime signatures, effects and call cycles agree with the compiler. |
| `tools/rtabi.py` | LLVM signatures agree across runtime parts and corpus calls. |
| `tools/rtcheck.py` | Run subset algorithms on CPython against CPython behavior. |
| `tests/cache.sh` | Verify rebuilding and publishing rules with both compilers. |

The CPython implementations of `_rt` in `tools/rt_cpython` represent strings one
character per byte. Runtime checks compare string operations, integer `math`,
hashing and formatting. CPython integers do not overflow at 64 bits, so compiled
differential tests cover overflow behavior; CPython also does not enforce subset
typing.

ASan covers both runtime parts during cached JIT/AOT builds; UBSan covers C only.
`tools/test_runtime_asan.py` verifies cached subset instrumentation and uses an
externally allocated string with a deliberately false length to demonstrate an
overread report. Its uninstrumented control misses that overread. Managed small
objects still share allocator arenas, so ASan does not yet give every managed
object an independent red zone or detect all use after collection. Those
allocator checks remain separate work. Subset arithmetic and byte primitives
also provide their own checks; bootstrap, independent CPython execution and
compiled comparisons address other compiler/lowering risks.

From the repository root:

```sh
python3 tools/rtcheck.py
make test-cache
make verify
```

See [testing](testing.md) for the full workflow and
[sanitizer settings](internals.md#environment-variables) for configuration.
