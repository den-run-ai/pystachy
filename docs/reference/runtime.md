# Runtime implementation reference

Read the [runtime guide](../runtime-in-subset.md) for the architecture and workflow.
This page specifies the private runtime interface used by `runtime.py`; it is not
an API for ordinary programs.

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
| `str_new(n)` | Allocate a zeroed buffer; `MemoryError` for negative sizes or sizes above `2**63 - 18`. |
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

## List storage

List headers remain scanned so their backing arrays stay reachable. `list(range(...))`
initially uses pointer-free backing because every element is an unboxed integer, including
for an empty range's minimum-capacity buffer. The list layout and mutation interface are
unchanged. Generic growth, copies and slices still allocate scanned backing; preserving
element kinds through those operations is a separate follow-up.

## Build and cache

The driver reads and compiles a source snapshot of `runtime.c`, its `ryu/` includes
and `runtime.py`, links the bitcode with `llvm-link`, then runs `opt -O2`. The C
part is built with `-fexceptions` so exceptions can unwind through runtime frames.
JIT uses an object compiled from the combined bitcode; AOT links that runtime into
the program.

Cache names have the form `build/runtime-py-<L>-<K>.bc` and `.o`. The content key
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

## Checks and test boundaries

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

C sanitizers cover `runtime.c`, while subset arithmetic and byte primitives provide
their own checks. A compiler or primitive-lowering bug can still miscompile the
runtime. Bootstrap checks, independent CPython execution and compiled comparisons
address different parts of that risk.

For commit-specific experiments and the original proposed migration order, see
the [historical evaluation](../archive/runtime-prototype.md).
