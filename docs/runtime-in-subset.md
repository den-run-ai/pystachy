# The runtime in the Pystachy subset

Pystachy's runtime has two parts: `runtime.py`, written in the same typed Python
subset as programs, and `runtime.c`, which provides memory management and native
services. Both JIT and AOT use them together as part of the normal build.

This guide covers the architecture, development workflow and private interface
used by `runtime.py`. Ordinary programs cannot use that interface.

- [Responsibilities](#responsibilities) and [writing runtime code](#writing-runtime-code).
- [Runtime ABI](#runtime-mode-and-abi), [private primitives](#private-primitives), [machine memory](#machine-memory) and [container storage](#list-set-and-dict-storage).
- [Build and cache](#build-and-cache), [verification](#verification) and [what remains in `runtime.c`](#what-remains-in-runtimec).

## Responsibilities

| Part | Responsibilities |
|---|---|
| `runtime.py` | String methods and ASCII escaping, `os.path`'s string functions, `str(int)` and `int(str, base)`, scalar and integer `math`, `math.hypot`/`dist`/`fma`, `any`/`all`, `sum`/`fsum`/`prod`, fixed-width integer division, remainder, shifts and bit counts, checked integer power and `pow(a, b, m)`, `round(int, n)`, range arithmetic, float-to-int conversion and rounding, the order of an int and a float, dict hashing, format-spec parsing, `str` concatenation and repetition, and the list header and item array with the operations that move or search items. |
| `runtime.c` | Collector, allocator, I/O, signals, exception unwinding, native library calls, float conversion and the container code not yet moved ([what remains](#what-remains-in-runtimec)). |
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

`int(x)`, `round(x)`, `math.floor`, `math.ceil` and `math.trunc` of a float convert with one
instruction where the float is within 64 bits, and call libm's rounding only beyond that,
out of line. `x / y` checks its divisor. The order of an int and a float compares floats
where the int is at most `2**53` in magnitude, and whole parts otherwise.

Fixed-width integer operators keep their existing ABI. Floor division and remainder
adjust truncation toward zero to Python's floor convention. Left shift checks for
lost bits by shifting the result back. Bit length and population count use the
magnitude as an unsigned bit pattern, including the magnitude of `-2**63`.
For true division, integers up to `2**53` in magnitude convert exactly to double.
Larger inputs use an integer quotient with extra rounding bits. A nonzero
remainder sets its low bit before conversion, preserving a single rounding to
binary64. A zero dividend retains the sign of the quotient.

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
  parameter's default value must be a literal. The only decorators are
  `@_rt.unchecked`, `@_rt.cold`, `@_rt.noinline` and `@_rt.inline`
  ([machine memory](#machine-memory)).
- A function that `RUNTIME` does not name takes and returns `int`, `float`, `str`,
  `_rt.Ptr` or `None`.
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
| `shl(a, n)`, `lshr(a, n)`, `ashr(a, n)` | Shift by `n % 64`. Right shift is logical for `lshr` and sign-extending for `ashr`. |
| `udiv(a, b)`, `urem(a, b)` | Unsigned division/remainder of 64-bit patterns; check zero. |
| `sdiv(a, b)`, `srem(a, b)` | Signed quotient truncated toward zero and corresponding remainder. Both check zero. For `-2**63` and `-1`, the quotient raises overflow and the remainder is zero. |
| `ctlz(a)`, `ctpop(a)` | Count leading zeros or set bits in a 64-bit pattern. A zero input has 64 leading zeros. |
| `mul_ovf(a, b)` | Test whether signed multiplication would overflow. |
| `mul_hi(a, b)` | High 64 bits of the 128-bit product of two 64-bit patterns as unsigned ints; `wrap_mul` gives the low ones. |
| `udiv_wide(hi, lo, d)`, `urem_wide(hi, lo, d)` | Low 64 bits of the quotient or remainder of unsigned 128-bit `hi:lo` divided by `d`. Both check zero. |
| `float_bits(x)`, `bits_float(i)` | A float's IEEE 754 bits as an int, and the float of such bits. |
| `fma(x, y, z)`, `sqrt(x)`, `fdiv(x, y)` | `x * y + z` rounded once, the square root and the quotient as IEEE 754 defines them: an inf or a NaN, never an error. |

The float primitives `ftrunc`, `ffloor`, `fceil` and `frint` round to a whole float as
libm's `trunc`, `floor`, `ceil` and `nearbyint` do, `copysign(x, y)` gives `x` the sign of
`y`, and `f2i(x)` truncates a float to an int where the result fits: the caller tests
that first. `ult(a, b)` and `ule(a, b)` compare two 64-bit patterns as unsigned ints.

Two lifetime rules are manual:

1. Only `str_put` and `copy` may modify a buffer made by `str_new`, and only before
   `str_done`. Nothing checks that a string has not already been published.
2. An omitted string parameter, such as `strip()`'s characters, is a null pointer.
   Test it with `null` before reading its length or bytes. Dereferencing it crashes.

String length and byte accesses carry alias-analysis metadata so LLVM can retain
lengths and optimize construction loops. Runtime-mode unit-step range increments
use LLVM's signed no-overflow form; runtime authors must keep the loop valid for
that assumption.

## Machine memory

The code that owns a layout reads and writes it directly, as `runtime.c` does. Runtime mode
has a raw address type and unchecked accesses for that code. Nothing verifies an index, a
field's record or a lifetime: the author keeps the invariants that C code keeps.

`_rt.Ptr` annotates a raw address. A `pys_*` function takes one where its `RUNTIME` entry
has a receiver, a list, a dict or another reference, and reads the layout it knows the
value to have. An address is a native reference to the typed IR, so the collector's
conservative scan sees it in a local as it sees a C pointer.

| Primitive | Contract |
|---|---|
| `nil()`, `null(p)` | The null address, and the test for it. |
| `ptr(i)`, `addr(p)` | An int as an address, and an address or any reference as an int. |
| `ref(x)`, `as_str(p)` | Any reference as an `_rt.Ptr`, and an address as a `str`. No instruction. |
| `word(p, i)`, `put(p, i, v)` | The 64-bit word `i` of an array at `p`: an item, a hash, a slot. |
| `byte_at(p, i)`, `put_byte(p, i, v)` | Byte `i` at `p`, read unsigned. |
| `i32_at(p, i)`, `put_i32(p, i, v)` | The 32-bit word `i` at `p`, read signed. |
| `at(p, i)`, `offset(p, n)` | The address of word `i`, and the address `n` bytes on. |
| `get(p, "R.f")`, `set(p, "R.f", v)` | The word field `f` of record `R` at `p`. |
| `getp(p, "R.f")`, `setp(p, "R.f", q)` | The address field `f` of record `R` at `p`. |
| `field(p, "R.f")`, `sizeof("R")` | A field's address, and a record's size in bytes. |
| `local("R")`, `words(n)` | A record, or `n` array words (a literal from 1 to 16), in the function's frame: C's `Buf b` and `I w[2]`. Unset until written; the collector scans them as it scans C's locals. |
| `cpy(d, s, n)`, `move(d, s, n)` | `memcpy` and `memmove` of `n` bytes. |
| `fill(p, c, n)`, `cmp(p, q, n)` | `memset`, and `memcmp`'s sign as an int. |

A record is one of `runtime.c`'s structs, listed with its fields in `RTRECORDS`
(`specs.py`): `Str`, `List`, `VTuple`, `Dict`, `Set`, the text `Buf` that `repr` grows, a
dynamic value's `Dyn` and `DynType`, and a class's reflection record `ReflRec`. The compiler addresses a field
through the record's LLVM type, so the target's layout places it; wasm32's four-byte
pointers need no second spelling. `tools/check_runtime.py` compares each record with the
struct that clang compiles. A field holds a word or an address, and reading one as the
other is a compile-time error.

Three rules keep LLVM's alias analysis sound. Loads and stores carry one of three tags: an
array's word, a record's word field, and a record's address field. LLVM assumes that a
store with one tag changes nothing read with another, which lets it keep a list's length
and item pointer in registers while a loop stores items. So:

1. Read and write a record's fields only with `get`, `set`, `getp` and `setp`, never as
   words of the record.
2. Read and write array words only with `word` and `put`. The inline items after a list's
   header and a companion's kind word are array words.
3. A `str`'s length has the tag of `len()`; its bytes are untagged through `byte_at`.

`cpy`, `move`, `fill` and `cmp` carry no tag and may touch anything.

Two decorators mark low-level functions. `@_rt.unchecked` gives `+`, `-` and `*` C's
signed arithmetic on sizes and indexes: no overflow check, and a result past 64 bits is
undefined, which lets LLVM reason about a size as it does in C. `<<` and `>>` shift by
their count modulo 64. Without the decorator those operators raise `OverflowError`, which
a function whose entry has no `R` may not do. Arithmetic that is meant to wrap says so
with `wrap_add`, `wrap_sub` and `wrap_mul`. `@_rt.cold` keeps a slow path out of line.
`@_rt.noinline` keeps a function that is not cold a call of its own, as the entry points
that hash a key are: copied into every use in a program's AOT build, they made
executables larger for no speed. `@_rt.inline` gives each caller its own copy, which
takes the caller's constant arguments.

`ord()` of a one-character ASCII literal is its code, a constant: the walks below compare
a descriptor's bytes with `ord("L")` and its kin.

A function with a result whose loops only a `return` leaves ends in a `return` that is
never reached. Without it the compiler raises for the missing result, and that raise
would give the function an `R` it does not have.

A runtime function whose `RUNTIME` result is a promoting int (`int+`, an LLVM
`{i64, ptr}`) is declared `-> tuple[int, _rt.Ptr]`. It returns its two words by value,
as the C function it replaces returned its struct: each `return` makes the tuple, which
the compiler returns as its slots (the same lowering that returns a fresh tuple to a
caller that only unpacks it), and the exported symbol turns the second into a pointer.
`runtime.py` may call such a function only to unpack its result; the compiler rejects
any other use, and a `return` of a tuple that the function did not make there.

`runtime.c` keeps what only it can provide: `pys_alloc` and `pys_alloc_atomic`, the page
map's answer to whether an array is scanned, the addresses of its static sentinels and the
opt-in test. `runtime.py` declares each as an external function. The runtime's `-O2`
inlines them, since both parts are one module by then.

CPython runs this code on a model of the heap that checks every access, the alias rules
above and the unchecked arithmetic: see [verification](#checks-and-test-boundaries). The
compiled tests cover it too, with the collector's stress modes, the sanitizer builds and
the list and dict probes.

## List, set and dict storage

The list header and its item array are `runtime.py`'s: new lists, growth, `append`,
indexed reads and writes, `pop`, `del`, `insert`, `extend`, slices and their assignment
and deletion, `copy`, `clear`, `reverse`, `+` and `*`. The rules below are what that code
implements. It follows `runtime.c`'s statements, including where a field is read again
after a call: a value held in a local across a rarely made call costs the common path a
saved register, which the JIT's runtime shows since nothing is inlined into a program
there. So are the searches (`in`, `index`, `count`, `remove`), which compare the slots of
ints, bools and strs themselves and ask `runtime.c` only where an item's `__eq__` may
run; `list(range(...))` and `list(bytes)`; and the promoting ints' companion with its
stores. The identity companion's entry points, `min`, `max` and sorting remain in
`runtime.c` and call it.

`str` concatenation, the joined parts of an f-string and repetition allocate their result
with the collector's unzeroed allocation and write every byte, as they did in C. Owned
appends (`s += t` into a buffer with room) stay with the collector's segment sizes.

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

A set's table is `runtime.py`'s as well: the probes, insertion, removal, the rebuilds,
merges and differences, comparison, iteration and `pop`, for 64-bit elements and for the
ints past 64 bits whose `Mpz` a second array holds. It is CPython 3.13's table, so a set
of ints iterates in CPython's order. `runtime.py` hashes ints and strs itself. For an
element that a type descriptor describes it calls `runtime.c`, whose hash and equality
may run the program's `__hash__` and `__eq__`: every loop that makes such a call reads
the table again afterwards, and starts again where CPython's does. The 8 slots of a new
or cleared set are scanned whatever its kind; a larger table of ints is atomic.

So is a dict's: the entries in insertion order, the index over them, the probes of int
and str keys, insertion, deletion and its holes, the rebuilds, `popitem`, the copies and
merges as CPython 3.13 sizes them, the views and a loop's steps. A lookup returns the
index slot of the key, or a value below zero that names the slot an insertion takes, so
that one probe serves both without a result in memory. An entry point that hashes a key
keeps `runtime.c`'s shape: the hash and the choice of probe are inlined into it, and the
probe is a function of its own. `runtime.c` keeps the hash of a key that a type
descriptor describes and the probes of such keys, which may run the program's code, and
four entry points whose result is two words. Each probe calls `pys_rt_probe`, which is
empty in the runtime and counts slots in `tools/dictprobe.c`.

Dict value arrays follow the same rule. The compiler makes a dict whose values are ints,
floats or bools with `pys_dict_new_atomic`, which sets the dict's `vatomic` word. Every value
array of that dict is then atomic, through growth and `clear()`, as are the value arrays of
its copies (`dict.copy()`, `dict(d)`) and `list(d.values())`. `dict.fromkeys` and an open
empty dict that a template returns are made scanned. Key arrays keep their own rule: those
of int keys are atomic. `tests/programs/runtime/gc_dict_values.py` and `make dictprobe` cover dict values.

## Repr, equality and ordering by descriptor

The compiler describes a value's static type with a descriptor, a str of letters (`L` a
list, `Ds` a dict of str keys, `T2if` a tuple, `?i` an optional int, `U2:1:i2:s` a tagged
union, `R4:` an edge back to an enclosing descriptor). `repr()`, `==` and the orderings of
a value whose code the compiler does not specialize walk it by its descriptor, and those
walks are `runtime.py`'s: `pys_repr`, `pys_eq`, `pys_eq_pair` (two descriptors of one
value, a union's member against an int) and `pys_cmpop`. They follow CPython's
comparisons item by item: identity before `__eq__` in a container, the first unequal
pair decides an ordering, a length is read again after each item's `__eq__`. A recursive
alias's 513th edge raises `RecursionError`, as `runtime.c`'s walks did.

`repr` grows its text in a `Buf` in its caller's frame (`_rt.local`), whose bytes double;
`runtime.c`'s messages pass their own. A str's repr copies each run of printable
characters at once, and escapes the others as CPython's `unicode_repr` does.

`runtime.c` keeps what the walks call: the marks of the reprs under way, which an unwind
clears; the program's own `__eq__`, ordering and `__repr__`; exceptions and dynamic
values; an `Mpz`'s digits and comparison with a float; a float's text; the table of
printable characters; and the errors whose text it formats without allocating. Its own
walks, the hashes of keys, dynamic values and the sort, step through a descriptor with
`runtime.py`'s `pys_rt_skip` and compare through `pys_rt_eqv`, `pys_rt_eqitem` and
`pys_rt_opv`.

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

[Machine memory](#machine-memory) runs on CPython too, on a model of the heap
(`tools/rt_cpython/rt_heap.py`): addresses are integers, an allocation is a block
with the allocator's byte of slack, and the parts of `runtime.c` that the memory
code calls have Python counterparts beside it. Nothing checks a compiled access;
the model checks each one, and `tools/rtcheck.py` reports as a failure:

| Fault | Compiled, it would |
|---|---|
| A read or write outside its block | Corrupt a neighbour or read its bytes. |
| A read of bytes that nothing wrote | Read what `pys_rt_raw` left there. |
| A typed read of a slot that another type last wrote | Let LLVM reorder the two: the [alias rules](#machine-memory). |
| A sum, difference or product past 64 bits in an `@_rt.unchecked` function | Be undefined, as in C. |
| An overlapping `_rt.cpy`, or a size below zero | Be undefined. |
| More reads in one operation than any real one makes | Never return: a loop without an end. |

The list operations run against CPython's own `list`, one operation at a time:
the result or the error, then the storage that `runtime.c` promises (capacity,
the kind of the item array, zeroed slots past the length, the emptied list's
sentinel). With an identity companion each item keeps the box that CPython's
object identity says it has, and with a promoting-int companion its `Mpz`. The
str operations are checked for their bytes, terminator and cached count.

The set operations run against CPython's own `set` in the same way. Of ints, of
ints past 64 bits and of objects with a `__hash__` of their own, the table must be
CPython's slot for slot: the elements come out in CPython's order after every
operation, which checks the probe sequence, the reuse of dummies and each resize
rule. Sets of strs are compared as sets, since a str's hash is not CPython's. An
`__eq__` that changes a set during a lookup must leave the tables sound; what such
a program prints is compared with CPython by the compiled tests.

The dict operations run against CPython's `dict`: int keys, str keys in both hash
schemes, objects with a `__hash__` of their own, and ints past 64 bits as keys and
values. After each operation the entries must be CPython's items in CPython's order,
every live entry must be on the probes of its hash, and holes and the entries past
the last must hold nothing that the collector would keep.

The walks run on values of random types laid out as `runtime.c` lays them out: lists,
dicts, sets, both kinds of tuple with promoting ints among their items, optional boxes,
unions and objects whose `__eq__`, ordering and `__repr__` are the program's. `repr` must
give CPython's text, `==` and the orderings CPython's answer or error, and `==` of the same
values under two descriptors (a union for an int, a counted tuple for a fixed one) the
answer for one. A recursive alias's 512th edge must pass and its 513th raise, and every
repr must end the marks it made.

The model's own checks are tested by faults made on purpose, and by seeded bugs in
the moved code, each of which the test's run finds
(`tools/test_rtcheck_memory.py`).

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

## What remains in `runtime.c`

The aim is a `runtime.c` that holds the collector, the allocator and the services only C
can reach: system calls, libc's float text conversion, signals and the unwinder. Python
semantics belong in `runtime.py`. [Machine memory](#machine-memory) is what lets the
container code move; the table gives the state and the order.

| Section of `runtime.c` | Lines | Plan |
|---|---:|---|
| Collector and page heap | 860 | Stays. |
| Exception unwinding and tracebacks | 860 | Stays: the Itanium ABI's tables and personality, and the line tables that a traceback reads. |
| I/O, processes, time, `select`, `errno`, temporary directories | 2,340 | Stays: system calls and libc streams. Buffering policy and text decoding can move later. |
| Unicode and other constant tables | 1,390 | Stay as data; `runtime.py` reads them through pure helpers. |
| Lists and tuples | 840 | Next: the identity companion's entry points, counted tuples, `min`/`max`, then the sort. |
| Strings | 620 | Slices, indexed text access and its hints, `chr`/`ord`, float text. Float formatting and parsing stay with libc. |
| Keys by descriptor: their hashes, equality and probes | 460 | Next: the walks they call are `runtime.py`'s. The tables of sets and dicts, and their entry points, are too. |
| Descriptor walks' services | 230 | Stays: the marks of reprs under way, boxes, reflection records and the errors formatted without allocating. The walks are `runtime.py`'s. |
| Dynamic values | 1,230 | After the keys: boxes, dispatch and the `Any` operators. |
| Promoting ints and `math` | 930 | Last: needs `mpz/` beside it. libm wrappers keep their LLVM-specific guards. |

Each step adds the records it needs to `RTRECORDS` and removes the accessors that
`runtime.c` then no longer has to export. What a section still needs from runtime mode
decides its place in the order:

| Needs | For |
|---|---|
| The checks moved with the code | The identity companion's entry points: `check_lean_companion.py` pins their text, and `test_runtime_list_identity.py` their cost, in `runtime.c`. |
| The address of a static | Text indexing (its position hints and the one-byte strs), the sentinels, dynamic values (each builtin type's descriptor and the small ints' boxes). Accessor functions stand in today. |
| A word read at any alignment | The byte scans that test eight or 32 bytes at a time. |

A result of two words, which promoting ints return (a 64-bit part and an `Mpz`), runtime
mode has: the dict and set entry points that return one are `runtime.py`'s. So it has a
record in a function's frame, which the sort's merge state needs next. Named integer
constants at module level would also replace the repeated literals.
