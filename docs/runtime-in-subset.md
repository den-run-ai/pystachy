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
| `runtime.py` | String methods and ASCII escaping, `os.path`'s string functions, `str(int)` and `int(str, base)`, scalar and integer `math`, `math.hypot`/`dist`/`fma`, `any`/`all`, `sum`/`fsum`/`prod`, checked integer power and `pow(a, b, m)`, `round(int, n)`, range arithmetic, dict hashing and format-spec parsing. |
| `runtime.c` | Collector, object and container memory layouts, I/O, signals, native library calls and float conversion. |
| [The compiler](../src/README.md) | Runtime compilation, checked primitives, runtime signatures and linking. |

Moving a function into the subset keeps its C symbol and signature. Programs
continue calling the same runtime entry points. LLVM can inline across the two
parts after their bitcode is linked.

Numeric migrations preserve native scalar and list representations: the scalar,
range, power and compensated-sum helpers allocate nothing on successful paths.
Range length retains its existing unsigned count encoded in an `i64`; callers
check whether that count fits the operation they perform. Float summation keeps
CPython's distinct first-item handling for an integer start, and applies a finite,
nonzero correction only after traversal.

ASCII escaping measures the output before allocating one string, then copies
ASCII spans and writes escapes. It reuses the runtime's UTF-8 decoder, including
its malformed-byte and surrogate behavior. The result remains a fresh string,
including for empty or already-ASCII input. Raw storage and the collector remain
in `runtime.c`.

`str(int)` counts the digits of the magnitude, allocates one string and writes it from
the last digit. Its arithmetic wraps where it cannot overflow, so it raises nothing but
the allocator's `MemoryError` and keeps the effects it had in C. `int(str, base)`
gathers the value below zero, where `-2**63` has room, and decides whether a digit fits
from one division for each call. Two steps remain in `runtime.c`: `pys_num_ascii` gives
the ASCII form of a string that has other characters, from the table of decimal digits,
and `pys_int_badlit` raises the error for a string that is no integer, whose message
holds the string's `repr()`. `float(str)` and the arbitrary-precision parser in
`mpz/mpz.c` use the same two steps.

`math.hypot` and `math.dist` are CPython's `vector_norm`. A first pass over the
coordinates finds the largest and a second sums their scaled squares, so that no copy
of them is kept and nothing is allocated. The scale, a power of two, is built from the
largest coordinate's bits (`_rt.float_bits`, `_rt.bits_float`); what each square's
float leaves out comes from `_rt.fma`, and the root from `_rt.sqrt`. `pow(a, b, m)`
works on unsigned values below `|m|`, whose products take 128 bits (`_rt.mul_hi`,
`_rt.urem_wide`), and finds a negative exponent's inverse by Euclid's algorithm in
wrapping arithmetic. `round(x, n)` of an int needs 64 bits alone: `10**19` is past
them, so a comparison decides that case. The int `sum` adds with the checked
arithmetic; where a program's lists may hold ints past 64 bits, the compiler narrows
the list before the call, as for `math.prod` (`NARROWED`).

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

## Unicode classification

`runtime.py` scans ASCII directly for `isalpha`, `isalnum`, `isdecimal`, `isdigit`
and `isnumeric`, and reads other characters as `uchar` does. A pure C helper,
`pys_unicode_flags`, returns a code point's flags from 9,120 bytes of constant tables
in `runtime.c`, without a search. The first 2,048 code points, which UTF-8 writes in
one or two bytes, index an array directly. Any other takes three loads through staged
tables, which keep each distinct block of values once. The helper allocates nothing
and has no locale or mutable state. Its distinct alpha, digit, decimal and numeric
flags preserve CPython's overlapping properties.

`repr()` escapes what is not printable from tables of the same layout that hold one
bit for each code point, 4,737 bytes. They are apart from the flags because every
program links them, and `repr()` copies a run of printable characters at once.

`tools/unicode_classification_tables.py --write` regenerates the tables from the
pinned CPython and `--check` compares them with all 1,114,112 code points. The table
check runs in `tools/rtcheck.py`; `tools/unicode_audit.py` compares each native
predicate result and `repr()` over the same entire range in JIT and AOT. Bytes
predicates keep their independent ASCII scan.

## Unicode case

`str`'s case methods map ASCII first. A string of fewer than 16 bytes, as most are, is
mapped by a test of each byte in the method itself, which also gathers the union of
its bytes to learn whether one is not ASCII. A longer string takes `mapstr`'s loops.
They are written in operations of the byte's width (`tolow`, `toup`, `toswap`), so
that LLVM maps sixteen bytes in about as many instructions, with a boolean reduction
for the bytes that are not ASCII. `title`, `isupper` and `islower` keep a test of
each byte: a short string gathers the union in that loop, a long one is scanned
separately (`nonascii`, also vectorized), and a string that begins with a byte that
is not ASCII goes to its characters at once. `istitle` notes such a byte where it
finds no ASCII letter. An ASCII letter of the other case decides `isupper` and
`islower` without a scan. Bytes methods use the same byte-width loops (`mapcase`).

For `lower`, `upper`, `swapcase`, `casefold` and `capitalize`, the ASCII loop has
already written the ASCII characters of the result, since none of them maps an ASCII
character by what is around it. `upatch` then visits only the characters that are not
ASCII and maps each in place: one that does not change needs nothing, and most others
map to as many bytes. Where a mapping has another count of bytes, as `"İ".lower()`
has, `ucasemap` maps the string anew. It fills a string of the input's size in one
pass (`mapu`), copies a shorter result, and counts and refills a longer one: no
character maps to more than three times its bytes. `title` always takes `ucasemap`,
because a letter's case depends on the character before it. `ucased` and `utitled`
are the three case tests. All follow CPython's `do_lower`, `do_upper`, `do_swapcase`,
`do_capitalize`, `do_title`, `do_casefold` and its tests. A byte that begins no
character is kept and has no case. `final_sigma` reads the context of a capital sigma
in both directions, as `handle_capital_sigma` does.

These loops read a character of two or three bytes with `utwo` and `uthree`, which
are small enough for LLVM to make part of each loop; `uchar` reads the rest. A loop
steps by the count of the reader that succeeded, not by a count taken from the bytes,
so that the processor can begin the next character before this one is read.

Three pure C helpers read 17,177 bytes of constant tables in `runtime.c`, laid out as
the property tables are. `pys_unicode_case_flags` returns a code point's upper, lower
and titlecase flags. `pys_unicode_case_map` returns its lower, upper, title or
casefold mapping as up to three 21-bit code points, from one of 279 records of four
signed distances and a pool of the 255 longer mappings. A block of 256 code points
without case is a zero in the first stage, so a character of a script without case
takes one load. `pys_unicode_case_ignorable` reads 2,841 of those bytes, a bit for
each code point in stages of their own: only the context of a capital sigma asks, and
a program that maps case then links no property table.

`tools/unicode_classification_tables.py` generates these tables with the property
tables. It reads every value from the pinned CPython's `str` methods, one code point
at a time, including the two properties that only context shows, and `--check`
reads the tables again for all 1,114,112 code points. `tools/rtcheck.py` fuzzes the
traversal against CPython, and `tools/unicode_audit.py` compares the native mappings,
tests and context properties of every code point in JIT and AOT.
[`bench/unicode_case`](../bench/unicode_case/README.md) compares these paths with
main's loops and with CPython.

## Private primitives

`import _rt` is available only in runtime mode. Its implementations operate on
subset `str`, `int` and `float` values and emit LLVM instructions or calls recorded
in the runtime table.

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
| `mul_hi(a, b)` | High 64 bits of the 128-bit product of two 64-bit patterns as unsigned ints; `wrap_mul` gives the low ones. |
| `urem_wide(hi, lo, d)` | Remainder of the 128-bit `hi:lo` by `d`, unsigned; check zero. |
| `float_bits(x)`, `bits_float(i)` | A float's IEEE 754 bits as an int, and the float of such bits. |
| `fma(x, y, z)`, `sqrt(x)`, `fdiv(x, y)` | `x * y + z` rounded once, the square root and the quotient as IEEE 754 defines them: an inf or a NaN, never an error. |

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
AOT links a precompiled runtime made from the cached bitcode and optimizes each program
against its interface. See the [JIT/AOT pipeline](internals.md#jit-aot-and-runtime-caching)
for the fallback rules.

Cache names have the form `build/runtime-py-<L>-<K>.bc`, `.o`, `.so` and `.target`;
the shared library is used on Linux. The AOT tier's precompiled runtime for `pys_plain`
0 or 1 adds `.aot0.o`, `.aot0.bc` and `.aot0.late.bc` (or `.aot1.*`) beside them, or
`.aot0.fail` (`.aot1.fail`) where it cannot be built.
The small `.target` file preserves the runtime's target triple and data layout;
JIT optimization applies them before folding object sizes and field offsets.
The content key
includes runtime and compiler bytes, C flags, disabled `PYSTACHY_OPT` passes and
LLVM tool identities. Host CPU information is included for flags such as
`-march=native`. The path/flag group `L` separates compiler and tool configurations.
When a new runtime is published, old entries in its group are removed, with their
precompiled AOT runtimes.

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
| `tools/check_runtime.py` | Runtime signatures, effects and call cycles agree with the compiler. The built runtime calls no name that only glibc 2.38 and later have (`__isoc23_strtol`): `runtime.c` reads its numbers itself. |
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
