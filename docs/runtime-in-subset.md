# Writing the runtime in the subset

This document evaluates moving `runtime.c`, and the repository's other C code (`tools/dictprobe.c`), into the Pystachy subset itself. It reports on a working prototype, measures it, and compares the approach with how other compilers and runtimes (Go, Rust, Zig, LLVM, Mojo, RPython, Codon and others) write their runtimes in their own languages.

It covers robustness, quality, compilation, performance, scalability, extensibility, code reuse, and the interaction with the two pieces of work in progress: the typed IR (`docs/typed-ir.md`, branch `claude/typed-ir-prep`) and the bug fixes of `claude/m0-correctness` and `claude/scalability`.

The prototype is stacked on `claude/typed-ir-prep` (commit `30b51d9`). Unless a section says otherwise, measurements were made on a 4-core x86-64 VM with LLVM 18.1.3 and CPython 3.13, as the README's are.

## Summary

- **Verdict: promising, as an incremental mechanism, not as a rewrite.**
  - The C runtime gets a second half, `runtime.py`, written in the subset and compiled by the compiler itself.
  - Functions move into it one at a time, keeping their C names and types. Programs call them exactly as before, so **no program's IR changes**: `make irsame` against `30b51d9` reports all 615 corpus programs identical.
  - The garbage collector, the memory layouts of lists, dicts and strings, files and signals stay in C. Every system surveyed in §3 keeps some native core. The collector stays native unless the language has a compiler-checked low-level regime for it (§3, item 7), which Pystachy does not.
- **What moved in the prototype:** 52 functions.
  - 47 of runtime.c's functions:
    - the `math` module's integer functions (6);
    - the 41 str methods, from `find` to `splitlines`, with `join`, `split` and `rsplit`.
  - 5 entry points carved out of runtime.c's code:
    - the two dict hash functions, from `hsh()`, which runtime.c's dict code calls on every lookup;
    - the format-spec mini-language, in 3 functions, from `pys_format()`. runtime.c keeps a 7-line dispatcher and the `snprintf` calls that write a float's digits.

  runtime.c loses 328 lines of code (2,470 → 2,142, comments and blank lines aside); `runtime.py` has 777 (1,030 with comments). The compiler gains 196 lines net (+204/−8).
- **How.** `pystachy rt runtime.py` compiles the file in a *runtime mode*:
  - functions named `pys_*` are defined under their C names, with runtime.c's types;
  - `def f(...) -> T: ...` declares a C function;
  - `import _rt` gives 16 primitives, each a few LLVM instructions with their checks: byte reads, an in-place string builder, `memchr`/`memcmp`, wrapping and unsigned arithmetic (§1.2).

  The driver links the result to runtime.c's bitcode in the cached runtime (`build/runtime-py.bc` and its `.o`), so the JIT and AOT tiers both use it, and LLVM inlines across the two languages.
- **Performance: at parity on whole programs, within 10% on most moved functions** (§2.4).
  - The eight programs of `bench/` execute 0.997 to 1.004 times the C runtime's instructions (callgrind), and the compiler compiles itself with 1.0% more.
  - Wall-clock timings on this shared 4-core VM vary by about ±5%. `bench/sieve`, whose machine code is byte-identical under both runtimes, measured from 0.95 to 1.06.
  - The first measurement found `words` and `dictkeys` 10% and 5% slower, all of it in `join` and `split`. Both were fixed (§2.4.2).
  - Microbenchmarks of the moved functions are in §2.4.2. A `find` that `memchr` speeds up 20-fold is the best case; `strip` on short words, at about 1.2, is among the worst.
  - Without the primitives, the same code is 3 to about 20 times slower (§2.4.3).
  - Programs that use format specs get 6% to 17% larger executables (§2.3).
- **What it buys.**
  - **Testing on CPython.** `runtime.py` is ordinary Python. `tools/rtcheck.py` runs it on CPython against CPython's own str methods, `math` and `format()`: 261,000 cases in about one second, with no compilation.
    - When the format code moved, rtcheck's new format fuzzer found that runtime.c gave the wrong error message for a repeated `,` or `_`.
    - A compiled differential review of the moved format code found no regression in about 210,000 cases. It did find that runtime.c cut format error messages at 511 bytes and at a NUL, and read the presentation type as a byte.
    - All three are fixed in `runtime.py`, with tests recorded from CPython (§2.2).
  - **Five more pre-existing bugs**, outside the moved code, turned up during the evaluation and are reproduced in §2.2:
    - undefined behaviour in integer division;
    - a stale length in list `==`;
    - two lax UTF-8 decoders;
    - class ids that overflow their three digits.
  - **Safety by default.** Ported code gets checked arithmetic and checked indexing. Two of the three integer overflows fixed in commit `452f29c` are in moved functions; in the subset both would have failed loudly instead of computing a wrong value. The moved code no longer uses fixed-size buffers: one of them, the format code's, did truncate messages.
  - **The roadmap's runtime code in Python.** The open issues imply about 9k to 18k lines of new runtime code, 3.5 to 7 times today's runtime.c (§2.5). Under the current architecture all of it would be C.
  - **Reuse.** The planned WebAssembly GC backend needs a runtime written in the subset (`docs/typed-ir.md` §7.3), and the typed IR's effects table can be inferred from it.
- **What it costs.**
  - A small private dialect (`_rt`) that must stay small and lowerable to every backend.
  - UBSan no longer covers the moved code; the subset's own checks replace it.
  - The runtime is now compiler output: a code generation bug can miscompile it. The bootstrap fixed point now covers `runtime.py`'s IR, and `rtcheck` tests it independently of the compiler.
  - The code is longer: 2.4 times the lines and 1.4 times the characters of the C it replaces.
- **Sequencing.** Keep the runtime ABI frozen while the typed IR's steps 4 to 15 run. Leaf functions can move now, because the move does not change programs' IR. Generic helpers (`pys_eq`, `pys_repr`, the sort) should move after typed-IR step 13, as templates.

## 1. The prototype

### 1.1 runtime.py and runtime mode

`runtime.py` sits next to `runtime.c`. The compiler compiles it as it compiles a program, with these differences (`Gen.rtmode`):

| | program | `runtime.py` |
|---|---|---|
| a top-level `def pys_x` | `define internal ... @f.pys_x` | `define ... @pys_x`, exported under its C name |
| `def f(...) -> T: ...` | rejected (Ellipsis) | `declare T @f(...)`: a `pys_*` function of runtime.c |
| module-level code | runs in `@main.init` | only functions, imports and docstrings: nothing runs it |
| computed default values, `global` | stored by `@main.init`; module globals are GC roots | rejected: nothing would store them, and nothing would scan them |
| classes | allowed | rejected for now (§5) |
| `import _rt` | `module '_rt' is not supported` | the primitives of §1.2 |
| `@main`, `@pys.roots`, `pys_obj_*` | emitted | not emitted: each program defines them |
| `for i in range(...)`, step ±1 | checked increment | `add nsw` (§2.4.3) |

These rules keep the ABI right:
- An exported or external function may not take or return `bool`. The runtime ABI passes bools as `i64` (`rtt`), and a `bool` would compile to `i1`. That mismatch links without a warning and is undefined behaviour.
- An exported function annotates every parameter and takes no `*args`: a template would not be exported under its C name.
- An operation that lowers to a function `runtime.py` defines calls that definition, and must use its types. `math.gcd()` inside `pys_m_lcm` calls `pys_m_gcd`.
- A function may not use the operation it implements. `math.gcd()` inside `pys_m_gcd` would lower to a call to `pys_m_gcd`. `Gen.rt` reports it at compile time. This is the recursion that other runtimes keep running into (§3: Rust's `memcpy` built from `mem::swap`, Zig's `strlen`). Only the direct case is caught: a cycle through runtime.c is not (§2.10).

`tests/errors/rt_*.py` checks each rule, and the rejections of the table above.

runtime.c keeps a prototype of every moved function, so its own code can still call them: `hsh()` calls `pys_hash_str`, and `pys_format` calls `pys_format_int`.

### 1.2 The primitives

`import _rt` exists only while `runtime.py` compiles (`RTL` in `pystachy.py`). Each primitive lowers to a few LLVM instructions:
- The ones that index check their ranges.
- `udiv` and `urem` check for zero.
- The other arithmetic primitives are defined for every input.
- `null` and `str_done` check nothing.
- Nothing checks that `str_put` and `copy` write only into a str that `str_new` made. That is the one rule a caller must keep.

| primitive | meaning | LLVM | Wasm GC (§2.7) |
|---|---|---|---|
| `byte(s, i)` | byte `i` of `s`; `IndexError` outside `0 <= i < len(s)` | one unsigned compare, `load i8` | `array.get_u` |
| `str_new(n)` | a new zeroed str of `n` bytes | `pys_alloc_atomic`, store the length | `array.new_default` |
| `str_put(s, i, c)` | set byte `i` of a str that `str_new` made | compare, `store i8` | `array.set` |
| `copy(d, at, s, lo, n)` | `d[at:at+n] = s[lo:lo+n]` | five compares, `memmove` | `array.copy` |
| `str_done(s)` | hand the str out; it is no longer changed | nothing | nothing |
| `same(a, i, b, j, n)` | `a[i:i+n] == b[j:j+n]` | `memcmp` | a loop |
| `find_byte(s, c, st, en)` | first index of byte `c` (0 to 255) in `s[st:en]`, or -1 | `memchr` | a loop |
| `find_sub(h, n, st, en)` | first index of `n` in `h[st:en]`, or -1 | `memmem` | a loop |
| `null(s)` | the null that callers pass for an omitted `str` argument | `icmp eq ptr` | `ref.is_null` |
| `wrap_add/sub/mul(a, b)` | 64-bit arithmetic that wraps | `add`/`sub`/`mul` | `i64.add`/... |
| `shl(a, n)`, `lshr(a, n)` | shifts by `n % 64`, logical to the right | `shl`/`lshr` | `i64.shl`/`i64.shr_u` |
| `udiv(a, b)`, `urem(a, b)` | unsigned division of 64-bit patterns | `udiv`/`urem` | `i64.div_u`/`rem_u` |
| `mul_ovf(a, b)` | whether `a * b` overflows | `smul.with.overflow` | a 128-bit check |

The string length loads and byte accesses that the primitives emit carry TBAA tags: a str's length and its bytes never alias. That lets LLVM keep the lengths in registers in a loop that builds a str, and vectorize it (§2.4.3).

There are no raw pointers and no pointer arithmetic. Every primitive works on a `str` or an `int`, so `runtime.py` stays lowerable to backends without linear memory (§2.7): each has a Wasm GC counterpart, either an instruction or a short loop. The systems research of §3 recommends exactly this.

### 1.3 Calling C

`def pys_fmt_float(m: float, ty: int, prec: int, alt: int) -> str: ...` declares runtime.c's function. That is how the format code gets a float's digits, which runtime.c writes with `snprintf`, as before. The form names only runtime.c's functions (`pys_*`), and `rtabi` checks that runtime.c defines each one, with the same types. A `str` crosses as runtime.c's `Str *`, never as a `char *`, so libc is reached through runtime.c.

### 1.4 Building, caching and the bootstrap

- **The cached runtime.** When the driver rebuilds `build/runtime-py.bc`, it does the following:
  - it compiles `runtime.c` with clang as before;
  - it compiles `runtime.py` in-process, with the compiler that is running;
  - it links the two with `llvm-link` and optimizes the result once with `opt -O2`. LLVM then inlines runtime.c's helpers into `runtime.py`'s code, and the reverse: `hsh()` gets `pys_hash_int` inlined.
  - Each step is a separate command whose status counts. A pipe would let a failed `llvm-link` leave an empty module in the cache.

  `runtime.o`, the JIT tier's precompiled runtime, is built from that bitcode, so the JIT tier gets the cross-language inlining too. The name says `runtime-py`: a compiler from before `runtime.py`, run with the same home, keeps its runtime.c-only cache apart. The driver stops at once when `runtime.py` is missing.
- **When the cache is rebuilt.** The cache is rebuilt when `runtime.c`, `runtime.py` or the running compiler is newer than it.
  - The running compiler is its executable, found through `PATH` as the shell found it when it was run by name, or `pystachy.py` under CPython. The claims audit of this document found the `PATH` case missing; it is fixed.
  - Another compiler may compile `runtime.py` differently. A stale cache would otherwise outlive a code generation change.
  - Regenerating the IR on every run would be exact, but costs 18 ms of a 34 ms JIT start.
- **The fixed point.** `make` and `make verify` now also check that the three stages emit the same IR for `runtime.py` (`pystachy rt`): 8,607 lines.
  - The Python-free stage of `make verify` rebuilds the runtime, `runtime.py` included, with the native compiler alone, and compares that IR too.
- **Compile cost.** The native compiler emits `runtime.py`'s IR in 18 ms; under CPython it takes 0.23 s. This cost is paid only when the cache is rebuilt.
- **dictprobe.** `tools/dictprobe.c` includes runtime.c to count probes, and runtime.c's hash functions now live in `runtime.py`. So `make dictprobe` and the `dict-probes` step link it with `runtime.py`'s IR.

### 1.5 Testing on CPython: rtcheck

`runtime.py` imports only `math` and `_rt`, so CPython can run it. `tools/rt_cpython/_rt.py` is the CPython version of each primitive. A Pystachy str holds bytes, and CPython sees them one character per byte (Latin-1), as `pystachy.py` reads its own sources.

`tools/rtcheck.py` calls every exported function directly on random inputs and compares the result and the error with CPython's:

| functions | reference |
|---|---|
| 41 str methods | CPython's str methods, on ASCII text, where Pystachy matches CPython exactly. The width methods also run on UTF-8 text. |
| 6 `math` functions | `math.gcd`, `lcm`, `isqrt`, `factorial`, `comb`, `perm`, where the result fits in 64 bits |
| 2 hash functions | runtime.c's former formulas, computed over unsigned 64-bit ints |
| format, for int, bool, float and str | `format()` on random specs, some of them malformed: NUL, control and non-ASCII presentation types, and specs of 600 bytes. runtime.c's `pys_fmt_float` is replaced by CPython's own float formatting, which is what it reproduces. |

- A default run makes 261,562 comparisons in about one second. It is a step of `make verify`.
- **Mutation check.** Eight bugs planted in `runtime.py` were all detected. They covered whitespace, centering, overlapping `count`, case mapping, `maxsplit`, line breaks, `rfind`'s start and the sign of `gcd`.
- **What it does not test.**
  - 64-bit overflow, because CPython's ints grow. The differential tests compile the same code and check that.
  - Types: CPython does not enforce them, so a variable used with two types runs there. The compiler rejects it when it builds the runtime.

### 1.6 What moved, and what stays in C

| area of runtime.c | moved | stays in C, and why |
|---|---|---|
| strings | 41 methods (with `join`, `split`, `rsplit` and `splitlines`, which sat among the list functions) | `pys_str` (allocation), `pys_str_get`/`slice`/`add`/`mul` (the compiler's lowering of `s[i]`, `s[a:b]`, `+`, `*`), `pys_str_eq`/`cmp`, `pys_ord`/`pys_chr`, repr and ascii escapes, `pys_str_float` (float repr through `snprintf`/`strtod`) |
| arithmetic | `math` gcd, lcm, isqrt, factorial, comb, perm | the operators the compiler lowers to (`//`, `%`, `**`, shifts), `pow(a, b, m)` (128-bit), the libm wrappers |
| repr, `==`, ordering | none | generic helpers that interpret type descriptors at run time and call back into the program. They should become templates (§2.8). |
| lists and timsort | none | list memory, and timsort (a list bounds check blocks `memmove` recognition: §2.4.3) |
| dicts | the two hash functions | the table itself: raw `int32` index arrays and `uint64` hash arrays |
| formatting | the format-spec mini-language | the dispatch on the descriptor, and float digits (`snprintf`) |
| I/O, process, signals, time, errno, tempfile | none | stdio, `errno`, signal handlers, system calls |
| the collector | none | stack and register scanning, the page map, raw memory |

### 1.7 How much more could move

Four inventories made for this evaluation classified every function and table of runtime.c at `30b51d9` into four tiers. They cover 2,472 lines, counted per function and table; the file has 2,665. `docs/runtime-inventory.tsv` lists each item with its tier, its size and what it needs.
- **A**: expressible in the subset as it was before this prototype.
- **B**: needs the kind of extension this prototype adds, or one like it: byte access, a builder, wrapping or unsigned arithmetic, `extern` declarations of libc, module-level constant tables.
- **C**: needs raw memory: addresses, struct layouts, pointer-free allocation of non-str data.
- **D**: must stay native: stack and register scanning, signal handlers, exit paths.

| area | A | B | C | D |
|---|---:|---:|---:|---:|
| strings | 247 | 223 | 6 | |
| timsort | 158 | | 26 | |
| lists | 46 | | 47 | |
| dicts | 31 | 75 | | |
| formatting | 15 | 119 | | |
| arithmetic | 59 | 139 | | |
| repr, `==`, ordering | 4 | 10 | 92 | |
| I/O, process, time, tempfile, errno | 84 | 339 | 40 | 60 |
| tables (`errno`, `isprintable`) | 5 | 378 | | |
| the collector | 17 | 4 | 189 | 37 |
| other | 7 | 10 | 5 | |
| **total** | **673 (27%)** | **1,297 (52%)** | **405 (16%)** | **97 (4%)** |

So about four fifths of runtime.c could be written in the subset with extensions of the size of `_rt`. Tier B is mostly I/O over libc and the two large constant tables. Tiers C and D, a fifth, are the collector, the list core and the descriptor-driven generic helpers. The classification is a judgment per function, so the split is approximate.

One inventory prototyped the dict in the subset, over `list[int]` tables. Lookups took 3.7 ns against C's 3.6 ns at 1,000 keys, and 13.8 ns against 8.9 ns at 100,000 keys. The gap at 100,000 keys comes from 8-byte index slots where C uses 32-bit ones, from an extra indirection, and from bounds checks. So the dict table is portable, but it needs 32-bit arrays and generic classes first.

## 2. Evaluation

### 2.1 Robustness

**Better.**
- **Checked by default.** In `runtime.py`, `+`, `-` and `*` raise `OverflowError`, and the primitives check their indexes.
  - **Evidence from runtime.c's history.** Commit `452f29c` fixed three integer overflows in runtime.c. Two of them are in functions moved here:
    - `math.lcm` negated a product of -2**63 and returned -2**63;
    - `str.split` counted a negative `maxsplit` down past -2**63.

    Written the same way in the subset, both would have raised `OverflowError` at the faulty operation instead of computing a wrong value. For `lcm` that is the documented 64-bit deviation. For `split` it would still have been a bug: CPython returns the whole split there. But it would have been a loud one.
  - The C code had to test for overflow by hand, and the tests were sometimes missing. For example, `pys_str_join` summed its parts' lengths unchecked. That sum cannot overflow in practice, but nothing in the code says so. In `runtime.py`, the check is there by default.
  - runtime.c's `comb` needed `unsigned __int128` to stay exact. `runtime.py` multiplies directly unless `mul_ovf` says the product would overflow, and otherwise reduces by a gcd first. No step overflows unless the result does.
- **Fixed buffers are gone** from the moved code: the format code's `char r[70]` digit buffer and its `failf` buffer of 512 bytes.
  - The second was too small. A spec of 600 bytes cut the `Invalid format specifier` message at 511 bytes, and `%s` stopped it at a NUL in the spec.
  - `runtime.py` reports the whole spec, as CPython does (§2.2).
  - The float digits keep their C buffer, inside `pys_fmt_float`.
- **The bugs found by testing against CPython** (§2.2) are a robustness gain of their own: errors are now reported the way CPython reports them.

**Worse, or different.**
- **UBSan.** `make verify`'s UBSan stage instruments C only. `clang -fsanitize=undefined` adds no checks to `.ll` input, so it no longer covers the moved code.
  - The moved code cannot have the undefined behaviour UBSan looks for. Its arithmetic is checked or explicitly wrapping, and its memory accesses go through checked primitives.
  - The remaining risk is a bug in a primitive's lowering, which is about 70 lines of `Gen.primitive`, or a `str_put` into a str that is already shared (§1.2).
- **A compiler bug can now break the runtime.** Before, a code generation bug miscompiled programs; now it can also miscompile the runtime they link. Three things contain it:
  - the fixed point covers `runtime.py`'s IR;
  - `rtcheck` tests the same code without the compiler;
  - the differential tests run every program against CPython.
- **Errors raised inside runtime code.** A primitive's check (for example `IndexError: string index out of range` from `byte`) would surface as the program's error. That is better than a wild read, but it names nothing in the program. None of the tests triggers one: a check that fires means a runtime bug.

### 2.2 Quality and testability

- **One language for the semantics.** The moved functions now read like the CPython behaviour they implement. `pys_str_count` is a loop over `search()` instead of `memmem` pointer arithmetic.
- **Differential testing in-process.** `rtcheck` is the RPython idea (§3): run the runtime on the host interpreter.
  - It compares about 300,000 cases per second against CPython itself (261,562 in about 0.9 s). The differential test suite compiles each program twice and runs it.
  - On its first run, its format fuzzer found that runtime.c reported `Cannot specify both ',' and '_'.` for `f"{x:,,}"` and `f"{x:__}"`. CPython reads `,` and then `_`, so a second `,` or `_` is taken as the presentation type: `Cannot specify ',' with ','.` The fix is three lines of `runtime.py`.
  - A compiled differential review of the moved format code ran about 210,000 cases, JIT and AOT, under GC stress too. It found no regression, and found that runtime.c:
    - cut `Invalid format specifier` messages at 511 bytes (its `failf` buffer) and at a NUL in the spec;
    - read the presentation type as a byte, so a NUL type was taken as no type, and a non-ASCII or control type gave the wrong error.

    CPython reads a code point, and writes types outside 33..127 as escapes (`'\xe9'`). The fix is about 50 lines of `runtime.py`, which CPython checked against `format()` on 771,469 cases. `rtcheck` now generates such specs.
  - Five tests recorded from CPython cover these fixes. The compiler of `30b51d9` fails all five:
    - `tests/rt_format_comma_twice.py`;
    - `tests/rt_format_underscore_twice.py`;
    - `tests/rt_format_long_spec.py`;
    - `tests/rt_format_nul_spec.py`;
    - `tests/rt_format_type_code.py`.
- **Another bug found during this evaluation**, outside the moved code: class ids in type descriptors are written with `{:03d}` by the compiler and read as exactly three digits by runtime.c's `ocls`. With more than 1,000 classes in containers, `repr([C1000()])` calls `C100.__repr__`.
  - The repro is 1,002 classes, each put in a list and printed. It prints `[C100]` where CPython prints `[C1000]`.
  - It is not fixed here, because the fix changes descriptors in programs' IR.
- **Two more bugs, in code not moved yet.** runtime.c has three UTF-8 decoders. The strict one is `u8char`. The lax copies in `pys_ascii` and `asciinum` accept overlong forms and code points above U+10FFFF:
  - `ascii(chr(0xC1) + chr(0xBF))` prints `'\x7f'`, where CPython prints `'\xc1\xbf'`;
  - `int(chr(0xE0) + chr(0x99) + chr(0xA0) + "7")` returns 7, reading the overlong bytes as U+0660 ARABIC-INDIC ZERO, where CPython raises `ValueError`.

  Both were reproduced with the compiler of `30b51d9`. One decoder in `runtime.py`, tested on CPython, would fix them by construction. `int()`, `float()` and `ascii()` are next on the list (§5).
- **Two more, which the subset would make impossible or loud.** Both were reproduced with the compiler of `30b51d9`.
  - **Undefined behaviour in `pys_idiv`.** It calls `__builtin_clzll(0)` when the dividend is 0 and the divisor is above 2**53. With UBSan, `k / (1 << 60)` for `k == 0` aborts: "passing zero to clz(), which is not a valid argument". Without it, the result is right by luck. No test reaches it, so `make verify`'s UBSan step did not see it.
  - **A stale length in list `==`.** `eqv` compares the two lengths once, then reads both lists' slots. If an `__eq__` empties the other list, it reads zeroed slots and passes a null object to the next `__eq__`. The program dies with `AttributeError: 'NoneType' object has no attribute 'v'` where CPython prints `False`.

  In `runtime.py`, the first cannot happen: there is no undefined arithmetic. The second would be an `IndexError` from a checked read, not a null object; a faithful port re-reads the lengths, as CPython's `list_richcompare` does.
- **Two shared deviations found and left as they are**, in both runtimes:
  - A format width or precision above 10**8 raises `Too many decimal digits in format string`, where CPython accepts it. The README does not list this.
  - `"%c" % 233` writes the byte 0xE9, the `chr()` rule, where `f"{233:c}"` writes UTF-8 as CPython does.
- **Review.** A change to a moved function is a change to Python code that `rtcheck` exercises in a second. A change to runtime.c needs the full test suite and a sanitizer build.

### 2.3 Compilation and bootstrap

| | `30b51d9` (C runtime) | prototype |
|---|---:|---:|
| `make verify`'s bootstrap step (both fixed points for the prototype) | — | 24.6 s |
| cold runtime build (`build/runtime*.bc` and `.o`), plus hello world | 1.87 s | 2.15 s |
| `runtime.py` to IR | — | 18 ms native, 0.23 s under CPython |
| hello world, JIT, warm cache | 34.1 ms | 33.7 ms |
| AOT build of `bench/words.py` | 0.409 s | 0.426 s |
| compiler compiling `30b51d9`'s `pystachy.py` to IR | 0.167 s | 0.172 s |
| cached runtime bitcode / `.o` | 202 KB / 201 KB | 252 KB / 210 KB |
| AOT executables: hello world, `fib`, `sieve`, `words` | 24,008 to 62,624 B | the same (±0.1%) |
| AOT executables that use format specs: `dictkeys`, `nbody`, `dictlookup`, `spectral` | 49,672 to 75,048 B | +6%, +16%, +16%, +17% |
| native compiler | 1,007,040 B | 1,040,400 B |

- A cold runtime build costs 0.28 s more: `runtime.py`'s IR, `llvm-link`, and one `opt -O2` over the linked module. A warm cache costs nothing: the JIT tier's startup is unchanged.
- The cached bitcode grows by 25% because it holds `runtime.py`'s code before `--only-needed` linking. The JIT tier's `runtime.o` grows by 4%.
- AOT executables that format numbers grow by about 8 KB. `runtime.py`'s `fmt()` with its checks and error paths is larger than runtime.c's `pys_format` was. The others do not grow.
- The native compiler grows by 3%, which is its own new code (runtime mode, primitives, driver).
- **New coupling.** The runtime now depends on the compiler that builds it. CPython's compiler, stage 1 and stage 2 must agree on `runtime.py`'s IR, and `make` checks that they do. The rule "a newer compiler rebuilds the cache" makes the first run after a rebuild of the compiler slower, by about 2 s for clang, `runtime.py` and `opt`.

### 2.4 Performance

All timings: best of 5 to 11 runs, AOT (`pystachy build`) and JIT (`pystachy run`, compilation included). "C" is the compiler and runtime of `30b51d9`; "subset" is the prototype. Outputs are checked against CPython on every run.

#### 2.4.1 Workloads

| benchmark | AOT C | AOT subset | ratio | JIT C | JIT subset | ratio |
|---|---:|---:|---:|---:|---:|---:|
| fib | 0.033 | 0.033 | 1.00 | 0.071 | 0.068 | 0.96 |
| mandel | 0.036 | 0.035 | 0.99 | 0.082 | 0.074 | 0.90 |
| nbody | 0.030 | 0.030 | 1.00 | 0.084 | 0.084 | 1.00 |
| spectral | 0.014 | 0.014 | 1.00 | 0.133 | 0.133 | 1.00 |
| sieve | 0.123 | 0.117 | 0.95 | 0.183 | 0.193 | 1.05 |
| words | 0.047 | 0.051 | 1.08 | 0.097 | 0.099 | 1.02 |
| dictkeys | 0.154 | 0.162 | 1.05 | 0.243 | 0.241 | 0.99 |
| dictlookup | 0.352 | 0.361 | 1.02 | 0.421 | 0.423 | 1.01 |
| the compiler compiling `30b51d9`'s `pystachy.py` to IR | 0.167 | 0.172 | 1.03 | | | |

The compiler is the largest string-handling program available, and both compilers emit the same 4 MB of IR. A callgrind profile of it (against the non-inlined `runtime.o`) shows where its time goes:
- `str ==` through the generic `pys_eq`: 31.5% of instructions;
- the collector: 13%;
- `pys_str_add`: 5.4%;
- `startswith`: 4.1% (moved here);
- `str(int)`: 3.5%;
- `find`: 2.0% (moved here).

So the moved methods are a real part of its work, and the biggest item, `==`, is a typed-IR change (§2.8).

`tools/dictprobe.c`, with its hash functions now in `runtime.py`, counts the same slots on all 49 rows. Its timings match runtime.c's: the median ratio over the rows is 1.000, and every row is between 0.98 and 1.03. LLVM inlines the subset functions into runtime.c's lookup loop.

#### 2.4.2 The moved functions

| microbenchmark (`tools/rtbench/`) | AOT C | AOT subset | ratio | JIT ratio |
|---|---:|---:|---:|---:|
| `t.find(w, i % 7)`, 200 KB text, word absent | 0.043 | 0.002 | 0.05 | 0.46 |
| `count("ab")`, `count("a")`, dense matches | 0.137 | 0.149 | 1.09 | 1.13 |
| `"mm" in w`, short words | 0.089 | 0.104 | 1.17 | 1.10 |
| `w.startswith("prefix")`, short words | 0.052 | 0.059 | 1.13 | 1.08 |
| `w.isdigit()` | 0.099 | 0.103 | 1.04 | 0.94 |
| `w.strip()`, short words | 0.032 | 0.038 | 1.18 | 1.01 |
| `split()`, 200 KB | 0.031 | 0.035 | 1.13 | 1.10 |
| `split(",")`, 140 KB | 0.037 | 0.037 | 0.99 | 1.02 |
| `replace("at", "og")`, 115 KB | 0.029 | 0.029 | 1.01 | 1.07 |
| `upper()` + `lower()`, 120 KB | 0.031 | 0.035 | 1.12 | 0.99 |
| `",".join(10,000 parts)` | 0.014 | 0.019 | 1.32 | 1.06 |
| `zfill`, `ljust`, `center` | 0.098 | 0.092 | 0.94 | 0.93 |
| `math.gcd` | 0.203 | 0.203 | 1.00 | 1.00 |
| `math.comb`, `factorial`, `isqrt` | 0.022 | 0.027 | 1.23 | 1.05 |
| f-strings with int, float and str specs | 0.463 | 0.476 | 1.03 | 1.05 |
| **median** | | | **1.09** | **1.05** |

- **Where the subset wins.** `find` with a rare first byte runs 20 times faster. `search()` looks for the needle's first byte with `memchr` (AVX2 in glibc). runtime.c called glibc's `memmem`, which for short needles runs a scalar byte loop; it uses Two-Way only for needles over 256 bytes. This is a best case. With dense matches (`count_ab`), an inline 16-byte scan before `memchr` keeps the cost close to `memmem`'s.
- **Where it loses.**
  - `join` (1.32) pays five bounds checks and a `memmove` per part, where C has an unchecked `memcpy`.
  - `strip` (1.18) tests the `null` default for each byte.
  - `comb` (1.23) executes 20% fewer instructions than runtime.c's but is slower: runtime.c's `comb` and `isqrt` were inlined into the benchmark's loop, and `runtime.py`'s are not.
  - All three are small, local fixes.

#### 2.4.3 What the primitives are worth

Without primitives, the subset can only read a byte as `ord(s[i])` and build a str from a `list[str]`. Three measurements show the cost:

| kernel | C | plain subset | with primitives |
|---|---:|---:|---:|
| `isascii` over 1 MB (ABI probe, AOT) | 5.6 ms | 48 ms (8.5×) | 5.5 ms with a byte read |
| `upper` over 1 MB (ABI probe, AOT) | 15–18 ms | 285–388 ms (about 20×) | `upper()` above: 1.12× |
| substring count, 1 MiB × 100 (codegen probe) | 0.295 s | 0.902 s (3.1×) | `count()` above: 1.09× |
| binary insertion sort, 40,000 ints (codegen probe) | 0.179 s | 0.950 s (5.3×) | 0.180 s without list bounds checks |

- **The byte read.** `ord(s[i])` is two runtime calls per byte (`pys_str_get` calls `pys_chr`, then `pys_ord`), and LLVM inlines neither.
- **Building a str.** Without a builder, a str has to be built from a `list[str]` and `join`, or quadratically with `+=`. The codegen probe measured 0.38 s for 80,000 `+=` appends, where CPython takes 0.004 s.
- **List bounds checks** stop LLVM from turning the element-shifting loop of an insertion sort into `memmove`. That is why timsort stays in C for now (§5).

**Two code generation findings came from writing runtime code in the subset.**
1. **`for i in range(...)` steps with `llvm.sadd.with.overflow`.** LLVM's scalar evolution cannot see through it, so it cannot prove `i >= 0`.
   - The effect: the unsigned bounds check in `byte(s, i)` stays, and the loop does not vectorize.
   - With a step of ±1 the increment cannot overflow, because `i < stop` (or `i > stop`), so `add nsw` is exact.
   - Runtime mode emits `add nsw`. That made `pys_hash_str`'s loop the same machine code as runtime.c's, and took `bench/dictkeys.py` from 1.10 to between 1.00 and 1.05 across runs.
   - In programs, the same change makes the compiler compile itself 5% faster (0.170 → 0.161 s) and leaves the benchmarks unchanged. All 1,009 tests pass and the fixed point holds.
   - It is not applied to programs here, because it changes every program's IR. It belongs to the typed IR's re-baseline (step 16).
2. **TBAA.** Without alias information, LLVM reloads a str's length after every byte store into a new str. The primitives' tags (§1.2), plus one loop per case mapping, let `upper()` vectorize: 1.63 → 1.12.

#### 2.4.4 Build cost and size

See §2.3: a cold runtime build takes 0.28 s more, and AOT executables do not grow.

### 2.5 Scalability

- **The runtime is about to grow several-fold.** An estimate made for this evaluation, from the open issues (#4 to #12) and the typed IR plan, puts the new runtime code the roadmap needs at roughly 9k to 18k lines:
  - M1: `fsum`, `dict.update`/`popitem`/`fromkeys`, `hex`/`oct`/`bin`;
  - M4: tagged values with CPython's `TypeError`s;
  - M5: an error flag at about 130 failure sites;
  - M6: native `collections`, `re`, `json`, `logging`, ...;
  - M7: `set`, `bytes`, `str.format`, big ints;
  - typed IR §7.1: `dict.find`, `entry_val`, `entry_set`.

  Today all of that would be C. Most of it is semantic code of the kind moved here: parsing, formatting, string algorithms, dispatch with CPython's error messages.
- **Compile time stays linear.** `runtime.py` is compiled once per cache rebuild, in 18 ms for 7,971 lines of IR, and the compiler's time is linear in its input (`tools/scaling.py`).
- **The C core stays small and stable.** The collector, memory layouts and I/O changed least on the stack: 93% of the stack's runtime.c additions were new functions appended at the end of a section.

### 2.6 Extensibility

- **Adding a builtin.** It takes a function in `runtime.py` and one line in `CALLS` or `METHODS`. Before, it took a function in runtime.c and that same line.
- **Who can write it.** Contributors write Python, with the subset's checks. They can test it on CPython before compiling anything.
- **Expressiveness.**
  - Everything in §1.6's "moved" column was expressible with the 16 primitives.
  - Code that needs raw memory (the collector, list and dict tables) or generic slots (the descriptor-driven `eq`/`repr`/sort) is not. That needs either templates (typed IR §7.3) or a pointer layer, which §6 argues against for now.
  - Classes are not allowed in `runtime.py` yet. A class kept in a container would need the program's `pys_obj_*` dispatch.
- **Templates (#2)** already make generic functions possible, but their instance names are not stable, so a template cannot be a C export today.

### 2.7 Code reuse

- **The WebAssembly GC backend** (README "Next steps", typed IR §7.3) cannot reuse runtime.c at all. Wasm GC objects do not live in linear memory, so C cannot touch them.
  - `docs/typed-ir.md` already plans "a runtime written in the subset, whose generic helpers are Pystachy templates".
  - Every `_rt` primitive has a direct Wasm GC counterpart (§1.2). The moved functions would compile for that backend unchanged, once lists and strs are Wasm arrays.
  - This is how dart2wasm and Kotlin/Wasm are built: their Wasm GC runtimes are Dart and Kotlin over a small intrinsics layer (§3).
- **The CPython-extension mode** (#4 §4) keeps Python objects as they are and does not use the standalone runtime. The moved functions could still serve it where they work on values the boundary converts (`str` → bytes). Nothing is gained or lost today.
- **Duplication with `lib/`.**
  - runtime.c's `pys_realpath` (added on `claude/m0-correctness`) is a 60-line C port of `posixpath.realpath`, which `lib/posixpath.py` already holds.
  - With functions as runtime code in the subset, such ports can share code with `lib/`, once the subset has what `posixpath.realpath` needs (`os.getcwd`, try/except).
- **The typed IR's effects table.**
  - Its `RUNTIME` table gives every runtime function its effects by hand, and `tools/check_runtime.py` is planned to check that table against runtime.c's prototypes.
  - For functions in `runtime.py`, the compiler can compute effects from their code, as it will for program functions (typed IR §3.7).

### 2.8 The typed IR

- **No interference with the migration.** The migration checks every step with `tools/irsame.sh`, which compares programs' IR byte for byte.
  - `irsame` never sees the runtime, and the prototype changes no program's IR: all 615 programs are identical.
  - Runtime-mode code paths (`rtmode`, `primitive`, `extern`, the nsw increment) run only for `runtime.py`.
- **Conflicts.**
  - The prototype edits `Gen.rt`, `Gen.function`, `Gen.declare_fn`, `Gen.program`, `Gen.builtin` (where `_rt.` calls go to `primitive()`), `for_range` and the driver. The IR steps rewrite all of these.
  - The edits are small: 196 lines net, most of them in `primitive()` and the driver. They would move into the lowering with the code around them.
  - `primitive()` is exactly an IR op set (`byte`, `str_put`, ...), and would become `Ins` ops after step 12.
- **What to keep frozen.**
  - The runtime ABI, as `docs/typed-ir.md` §2 asks.
  - The design of step 4 (the `RUNTIME` table), which should let a key bind to a C symbol or to a `runtime.py` function. `check_runtime.py` should read `runtime.py`'s signatures as well as runtime.c's prototypes.
- **Synergies, in order of value.**
  1. **Exceptions (§7.2 there).** The error-flag design was chosen partly because "the C runtime calls user code back from timsort and from `pys_eq`/`pys_repr` … landing pads would have to unwind through those C frames". Callbacks from `runtime.py` code have no C frames. Once the generic helpers move, landing pads become an option again.
  2. **Generic helpers as templates.** `pys_eq`, `pys_repr`, `pys_list_find`, `minmax` and the sort interpret a type descriptor at run time and call back through `pys_obj_*`. As `runtime.py` templates, they would be instantiated per type:
     - the `U?` effect becomes exact;
     - the descriptor-and-callback ABI (and the class-id bug of §2.2) goes away;
     - the Wasm backend gets them for free.
  3. **One layout definition.** The compiler and runtime.c both hard-code `Str`, `List` and `Dict` layouts today. Moving the accessors into `runtime.py` is a step toward a single definition.
- **Sequencing.**
  - Leaf functions can move at any time.
  - Generic helpers should move after step 13, when `rt` keys are the binding point.
  - Anything that changes programs' IR should wait for step 16's re-baseline. That covers the nsw increment and a fused `ord(s[i])`.

### 2.9 The ongoing bug fixes

- **Conflict risk is low.** No branch after `claude/scalability` touches runtime.c. typed-ir-prep and scalability carry the same blob.
  - Of the stack's 71 non-merge commits (`main..30b51d9`), 8 touched runtime.c, mostly adding functions at the end of sections.
  - The functions moved here were last changed on `claude/modules-and-templates` (`pad`, the split helpers) and `claude/scalability` (`hsh`). The prototype is stacked on both.
- **Coordination.** Future fixes to a moved function go to `runtime.py`, with a regression case in `rtcheck` where CPython can serve as the reference. This applies to the sessions working from #4, #13–#17 and the M-issues.
- **Where conflicts will come from.** The dict core (typed-IR §7.1's fused lookups, M1, M4, M7's sets) and M5's error paths, which touch every `pys_fail`. Neither is moved here.
- **Fixes get cheaper.** The separator bug of §2.2 is one example: the fuzzer found it, the fix is three lines of Python, and `rtcheck` confirms it in a second.

### 2.10 What an adversarial review found

Six independent reviewers attacked the prototype before it was submitted. Each had one lens: the str methods, the format/math/hash code, the compiler changes, GC and memory safety, worst-case performance, and this document's claims. Their reproducers compare CPython, the compiler of `30b51d9` and the prototype, JIT and AOT.

- **Equivalence.**
  - The str reviewer read every moved function beside its C. It ran loop programs over the edge cases: indexes from INT64_MIN to INT64_MAX, every `maxsplit`, every line break, fills, tab sizes, raw and UTF-8 bytes. Base and prototype agreed everywhere.
  - The format/math/hash reviewer ran about 210,000 compiled cases, under GC stress too, and 32,203 math cases at the 2**63 boundary. It checked 4 million hash values against the old formulas. It found no regression.
- **Regressions in the prototype, found and fixed before submission.**

  | problem | effect | fix |
  |---|---|---|
  | `search()` checked every candidate with no bound on the work: O(n·m) | a 200,000-byte needle in 2 MB took 6.5 s against 0.006 s; a 20-byte needle in dense text took 17 times as long | a work bound with a cutover to `memmem` (`_rt.find_sub`). Both cases now take runtime.c's time, and `rtcheck` tests the cutover. |
  | `join` and `split` executed more instructions | `bench/words.py` +10% and `dictkeys` +5% in instructions | iteration instead of indexing, `memchr` per part for a one-byte separator. Both are now at 1.00. |
  | `strip(chars)` looped over the set for each byte | 14 times runtime.c's time with a 95-byte set | `memchr`, as runtime.c did |
  | `ljust` and friends within 9 bytes of 2**63 | `OverflowError` where CPython and runtime.c raise `MemoryError` | `_rt.str_new` reports such sizes as `MemoryError`; `tests/rt_ljust_huge.py` |

  `rtcheck` could not see any of these. The first four are performance problems, or differences between `_rt.str_new` and its CPython twin. Compiled differential tests at the edges, and performance tests with long needles, are what found them. `tools/rtbench/` now has three such cases (`find_dense`, `find_worst`, `strip_chars`), and §2.4.2 reports them.
- **Gaps in runtime mode and the driver, found and fixed before submission.** The compiler reviewer wrote a reproducer for each.

  | problem | effect | fix |
  |---|---|---|
  | `llvm-link ... \| opt -O2` took `opt`'s status | a failed link left an empty module in the cache, trusted from then on: every later run failed with missing symbols | no pipes (§1.4) |
  | an operation lowering to a function that `runtime.py` defines emitted a `declare` beside its `define` | invalid IR; it would have blocked moving any function that `runtime.py`'s own code uses, such as `pys_chr` | a call to the definition, with its types checked |
  | a computed default value, or `global` in a function | stored by module code that never runs, or a global the collector does not scan: a segfault, and a use-after-free under GC stress | rejected (§1.1) |
  | a `pys_*` template or `*args` function | not exported, without a word | rejected |
  | an extern named like a builtin, or a libc function | a mangled name; a `str` passed as a `char *` | externs are runtime.c's `pys_*` functions, and `rtabi` checks that runtime.c defines each |
  | `rtabi` skipped signatures with return attributes | a C `_Bool` return, the case it exists for, passed | it reads them, and checks itself on such lines |
  | compilers from before and after `runtime.py` sharing a home | each trusted the other's cache | the cache's name; `rtbench` ignores `PYSTACHY_HOME` |
  | the cache rule ignored a compiler run through `PATH` (claims audit), then looked in the current directory first; a missing `runtime.py` was tolerated | a newer compiler could reuse an older runtime | `PATH` only, as the shell searches it; an error at start |
  | a compile error in `runtime.py` | a temporary directory left behind on each run | `runtime.py` is compiled before it is created |
  | the JIT tier's `runtime.o` lost `PYSTACHY_CFLAGS` | `-march=native` no longer reached it | the flags are passed |
  | each `make` makes the cache stale | `tests/run.sh`'s workers each rebuilt it at once | `tests/run.sh` builds it first |

  Two gaps are left, with their fixes in §5. First, a cycle through runtime.c is not detected. If `pys_format_str` formatted with a nested spec, it would call runtime.c's `pys_format`, which calls `pys_format_str`, and the program would hang. Second, an edit to a source during a cache rebuild can leave a stale cache. runtime.c has had that second gap since the cache existed.
- **Improvements over runtime.c that the review found.** These are the format fixes of §2.2: message truncation, a NUL in the spec, and presentation types read as code points.
- **Shared deviations it found and left as they are.**
  - A format width above 10**8 is rejected.
  - `"%c" % 233` writes one byte.
  - `strip()` with non-ASCII chars, and `replace("", x)`, work byte by byte. This is the byte-string model, but the README lists only `split()`.
  - `expandtabs` accepts tab sizes above CPython's C int limit.

## 3. How other compilers and runtimes do it

| system | in the language | still native | low-level dialect | how it moved | measured effect | how it is tested |
|---|---|---|---|---|---|---|
| **Go** (1.4–1.5, 2014–15) | the runtime and GC: 122k lines of Go in `src/runtime` | per-arch assembly (8.5k lines for amd64, all OSes), cgo C | `unsafe.Pointer`; `//go:nosplit` (1,032 uses), `//go:linkname` (787), `nowritebarrier`; the runtime is compiled with `-+`, where a heap escape is an error | a C-to-Go translator, then hand edits, over 20 months; checked by bit-identical compiler output | Go 1.4: precise GC, heap 10–30% smaller, the runtime "slightly" faster thanks to the Go compiler's inlining. Go 1.5: builds about 2× slower, because the translated compiler was "unidiomatic Go code that performs poorly" | as an ordinary package (`export_test.go`), with GODEBUG stress modes |
| **Rust** | `core`, `alloc`, `std`, `compiler-builtins` (a port of compiler-rt, 8.8k lines) | an optional C fallback for builtins, libunwind | intrinsics, lang items, `no_std`, `#![no_builtins]` | one intrinsic at a time, with the C version as a fallback; 10 years on, still not complete | no aggregate study; builtins are kept out of LTO | against the host's compiler-rt/libgcc, and MPFR for libm |
| **Zig** | `compiler_rt` (23k lines plus 97k of tests, no C), libc functions moving into libzigc | about 2,000 bundled C files (Jan 2026) | `export`, weak/hidden symbols, `no_builtin`, `no_panic` | function by function, deleting each C copy | shipping the runtime as source, built lazily per target, is what makes cross-compiling work; the self-hosted compiler builds in a third of the memory | tests ported with each routine |
| **LLVM libc** | libc in C++ (326k lines) | 48 files with inline asm | `LIBC_INLINE`, no dependency between public entry points | new code, used beside the system libc | correctly rounded math; GPU builds ship bitcode for LTO | MPFR, exhaustive single-precision tests, differential fuzzing against the system libc |
| **Mojo** | the standard library (116k lines) | CompilerRT (1.2k lines of C++), AsyncRT (12k) | `__mlir_op` (256 uses), `__mlir_type`, `@always_inline("builtin")` | written in Mojo from the start | per its internal stdlib docs, library-defined `Int.add` stopped compile-time folding until `@always_inline("builtin")` was added | the stdlib's own tests |
| **RPython / PyPy** | the GC (incminimark, 3.5k lines; 15.8k for the memory layer) and the interpreter, in a Python subset | 10.9k lines of C support (dtoa, threads, signals) | `lltype`, `llmemory`, `llarena`, `llop` | designed that way | a full translation takes 20 to 45 minutes and 4 to 6 GB | **untranslated, on CPython**: the model for `rtcheck` |
| **Codon** (a Python-syntax LLVM compiler: the closest analog) | the standard library, `int`, `str`, `list` and `dict` included: 94k lines | 1.7k lines of C++ (allocation, print, locale, exceptions, regex) and the Boehm GC | `@llvm` functions with inline LLVM IR (758 of them), `Ptr[T]`, `@C` | written that way from the start | "rival C/C++ in performance" (CC'23); the library is tied to LLVM text | its own test suite |
| **Jikes RVM / MMTk** | the whole JVM, GC included, in Java | a small boot loader | `org.vmmagic`: unboxed `Address`/`Word`, intrinsics, `@Uninterruptible` | — | MMTk in Java (ICSE 2004): on micro-benchmarks about 5% slower than monolithic collectors and 60% faster than glibc's malloc thanks to inlining; up to 20% better total performance on real benchmarks. Its restricted Java kept it from libraries and other VMs, and it was later rewritten in Rust (mmtk.io). | a harness that simulates memory as a hash table of pages |
| **GraalVM Native Image** | the serial GC (25k lines of Java) | 3.9k lines of C helpers | `org.graalvm.word`, `@Uninterruptible` (711 uses in the GC) | — | — | runs hosted on HotSpot, with boxed words |
| **Nim** | `system`, the ARC/ORC memory management, the allocator, and a conservative refc GC: 19k lines | 1.1k lines of C headers | `cast`, `ptr`, `{.compilerRtl.}`, `{.push rangeChecks: off.}` | ORC became the default in 2.0 (2023) | ORC: 320 µs average latency against 65 ms for mark-and-sweep under forced collections | Valgrind and sanitizers |
| **Swift, Julia** | the standard library (150k lines), `Base` (139k) | the runtime and GC in C/C++ (50k lines; 152k) | the `Builtin` module; `Core.Intrinsics`, `llvmcall` | — | Julia's C runtime does not report all its roots, so MMTk's moving collector for Julia needed conservative stack scanning and object pinning (ISMM 2025) | — |
| **dart2wasm, Kotlin/Wasm, J2Wasm** | the whole Wasm GC runtime (33k, 28k and 7k lines) | host imports (strings, regex) | `dart:_wasm` (321 `wasm:intrinsic`), `@WasmOp` (210), `@Wasm("...")` | — | V8: a VM written in C "can't" be compiled to Wasm GC; Google Sheets' J2Wasm build ended about twice as fast as its JavaScript | — |
| **mypyc** (for contrast) | — | `lib-rt` in C over the C API (29k lines) | — | — | — | — |

Sources and line counts: the research notes behind this table measured each repository at its October 2026 head (`golang/go 8dfc83de`, `rust-lang/rust 0f6e5bf`, `ziglang/zig fbd733c` on Codeberg, `llvm/llvm-project 15e2ad97`, `modular/modular babedf5`) and cite:
- go.dev/doc/go1.4, go.dev/doc/go1.5, go.dev/s/dev.cc and the Go 1.3 compiler design (go.googlesource.com/proposal/+/master/design/go13compiler.md);
- rust-lang/rust#35437 and #109821;
- ziglang.org/news/goodbye-cpp;
- libc.llvm.org;
- mojolang.org/docs/reference/inline-mlir;
- rpython.readthedocs.io;
- the LLVM Dev Meeting 2025 talk "LT-Uh-Oh";
- the Codon paper (commit.csail.mit.edu/papers/2023/cc_Codon.pdf);
- the vmmagic paper (VEE 2009) and the MMTk ICSE 2004 paper;
- the MMTk-for-Julia paper (ISMM 2025);
- the Nim ORC announcement (nim-lang.org/blog/2020/12/08);
- the V8 Wasm GC porting post (v8.dev/blog/wasm-gc-porting);
- the Google Sheets Wasm GC case study (web.dev).

**What these systems have in common, and what Pystachy takes from them.**
1. **Nobody gets to 100%.** Each keeps a native core: Go's assembly, Mojo's C++ runtime, Rust's libunwind, Zig's remaining C. Pystachy keeps the collector, memory layouts and I/O in C (§1.6).
2. **There is always a small private dialect, and it is kept unstable**: Go's `unsafe` and directives, Rust's intrinsics, Mojo's `__mlir_op`, Kotlin's `@WasmOp`, RPython's `llop`. `_rt` is Pystachy's. Kotlin's and Dart's Wasm runtimes show why it should have no raw pointers: those would not lower to Wasm GC.
3. **Runtime code is compiled in a restricted mode**: Go's `-+`, Zig's `no_builtin`, Rust's `no_builtins`. Runtime mode restricts module code, classes and bools in signatures, and rejects self-lowering.
4. **The recurring bug is the compiler creating a call into the runtime from the runtime itself**: Rust's `mem::swap` becoming `memcpy`, Zig's LLVM 21 `strlen`, LTO's `memcmp` to `bcmp`. `Gen.rt` rejects the direct case of the compiler's own version of this; a cycle through runtime.c is not caught yet (§2.10). LLVM may still turn byte loops into `memcmp`/`memchr`/`strlen` calls, which go to libc, not to the runtime.
5. **The move is incremental, with both versions kept checkable**: Rust's C fallback, Zig's per-function deletions, Go's bit-identical output. Here the C version stays in git history, and `make irsame REF=30b51d9` and the differential tests compare against it.
6. **The payoff that has actually been measured is not raw speed.** It is precision and memory (Go's GC), tooling and portability (Zig), inlining across the old language boundary (MMTk, Go), and testing on a host (RPython, MMTk's harness, GraalVM's hosted mode). The prototype matches runtime.c's speed (§2.4); its gains are testing, safety and the backends.
7. **The library part moves first, and the GC last or never.** Codon (Boehm), Swift, Julia and Kotlin/Native keep their collectors native. The collector is written in the language itself only where there is a compiler-checked low-level regime: a no-allocation rule, `Address`/`Word` types and a simulated-memory test mode (RPython, vmmagic, SubstrateVM, Go, Slang). Pystachy has none of these yet. This is why §5 keeps the collector in C.
8. **Wasm GC forces the move.** Every Wasm GC compiler surveyed wrote its runtime in its source language over Wasm-instruction intrinsics, and none ported a collector, because the engine has one.
9. **The runtime dialect should stay a subset of the language, not a separate one.** MMTk's restricted Java cut the collector off from libraries and other hosts. Slang dropped objects altogether. RPython is remembered for "cryptic" errors. `runtime.py` is ordinary subset code, with the subset's error messages, that CPython also runs. That last property keeps Pystachy's bootstrap CPython-only: inline LLVM text, as in Codon's `@llvm`, would end it.

## 4. Risks and how the prototype handles them

| risk | handling |
|---|---|
| a code generation bug miscompiles the runtime | fixed point over `runtime.py`'s IR; `rtcheck` runs the same code on CPython, without the compiler; differential tests |
| a stale cached runtime after a compiler change | the cache is rebuilt when the running compiler is newer, found through `PATH` if need be (§1.4) |
| ABI mismatch between `runtime.py` and the program's declarations | no `bool` in exported or external signatures; `make verify`'s `rt-abi` step (`tools/rtabi.py`) requires one LLVM signature per function across `runtime.py`, runtime.c and the 301 programs of the corpus (1,131 uses), and reports a planted mismatch |
| self-recursion through a lowering | the direct case is rejected at compile time (`Gen.rt`); a cycle through runtime.c is not yet (§2.10, §5) |
| `_rt` grows into a pointer layer | the rule in §1.2: `str` and `int` operands only, one Wasm GC counterpart each |
| performance cliffs in subset code (bounds checks, `sadd.with.overflow`) | primitives, TBAA, nsw range steps; measure every move (§2.4) |
| merge conflicts with the typed IR and the bug fixes | no program IR changes; leaf functions only; ABI frozen (§2.8, §2.9) |
| loss of UBSan coverage | the moved code is checked by construction; UBSan still covers runtime.c |

## 5. Recommendation and next steps

**Recommendation:** merge the mechanism, and move code into `runtime.py` function by function. Write the roadmap's new runtime code there by default, and C only where §1.6 says C.

1. **Now, with this prototype.**
   - `runtime.py`, runtime mode, `_rt`, external declarations, the cache rule, the fixed point, `rtcheck`, `rtabi` and `rtbench`.
   - The 52 functions moved here.
2. **Next leaf moves, independent of the typed IR.**
   - `int()` and `float()` parsing. They need wrapping arithmetic; the digit tables would use a `str` as a table.
   - str `repr` and `ascii` escaping over one shared UTF-8 decoder, which fixes §2.2's two decoder bugs; `pys_str_list`; `str(int)`.
   - The M1 runtime gaps (#6): `math.fsum`, `modf`, `prod`, `dist`, `hex`/`oct`/`bin`, `dict.update`/`popitem`/`fromkeys` over the C dict API. Write them in `runtime.py` from the start.
3. **Small language and compiler work that runtime code needs.**
   - A call-graph check over `runtime.py`, with a table of runtime.c's calls back into it (`pys_format`, `hsh()`), that rejects a cycle through an export (§2.10).
   - A content stamp for the cached runtime (a hash of runtime.c, `runtime.py`, the compiler and the flags) in place of the mtime rule.
   - Allow classes in runtime mode, as long as none ends up in a container.
   - Accept module-level constants, which need an init hook and roots: the ABI notes count 8 functions that want static tables.
   - Unchecked list access proven by the typed IR's bounds hoisting (§7.1 there). Then timsort can move without the 5× penalty.
4. **After typed-IR step 13.**
   - The `RUNTIME` table binds keys to `runtime.py` functions.
   - The generic helpers (`pys_eq`, `pys_repr`, `list.find`, `minmax`, sort) become templates instantiated per type, without descriptors or `pys_obj_*` callbacks. That also fixes §2.2's class-id bug.
5. **At the typed IR's re-baseline (step 16).**
   - Apply the nsw range step to programs.
   - Fuse `ord(s[i])` into a byte read for programs too.
6. **With the Wasm GC backend.** Lower `_rt` to Wasm GC array ops and reuse `runtime.py`. Only runtime.c's core needs a Wasm counterpart, and the engine supplies the collector.
7. **Stay in C.** The collector, `Str`/`List`/`Dict` memory, files, signals, `errno`, time, float digits (`snprintf`/`strtod`) and the libm wrappers. Revisit the collector only together with precise roots for frames the compiler generates (RPython's shadow stack is the precedent), which C cannot provide.

**`tools/dictprobe.c`** stays C. It is a white-box test that includes runtime.c to count the slots its dict code visits, and it now links `runtime.py`'s IR for the hash functions. It could become a subset program once the dict table itself moves, with a probe counter in `runtime.py`.

## 6. Alternatives considered

| alternative | why not now |
|---|---|
| keep runtime.c as is | Works, but the 9k–18k lines of roadmap code (§2.5) would all be C, untestable on CPython, with UBSan as the main safety net. |
| a full port, collector included, with a pointer layer (RPython's `llmemory`) | A large `_rt` that cannot lower to Wasm GC. The conservative collector scans C stacks and registers either way, so it gains nothing. The systems in §3 that wrote their collector in the language itself all had a compiler-checked low-level regime first (§3, item 7). |
| the runtime as a `lib/` prelude compiled into every program | Every program's IR would change with every runtime edit, which conflicts with `irsame` and the typed IR's migration. The JIT tier would recompile the runtime on every run, or need the same cache. |
| Rust, Zig or C++ for the runtime | A second toolchain, outside the self-hosting and Python-free stages. It removes undefined behaviour but adds no CPython testability and no Wasm GC reuse. |
| a mechanical C-to-subset translator (Go's c2go) | The subset lacks pointers, so most of runtime.c would not translate. Go's translator also needed the C refactored first and produced "unidiomatic Go code that performs poorly". The leaf code that does translate is small enough to port by hand, and hand ports came out at C's speed. |
| inline LLVM IR in runtime functions (Codon's `@llvm`, Julia's `llvmcall`) | It binds the runtime to one backend's text, so the Wasm GC backend could not reuse it. CPython could no longer run `runtime.py`, which would lose `rtcheck` and the CPython-only bootstrap. `_rt`'s primitives are operations each backend lowers, as Julia's intrinsics and Mojo's `pop` dialect are. |

## Appendix A: what the prototype changes

| file | change |
|---|---|
| `pystachy.py` | +204/−8 lines:<br>• runtime mode (`rtmode`, exported and external functions, `RTL` and `primitive()`, nsw range steps);<br>• `pystachy rt`;<br>• the driver's runtime build and cache rule |
| `runtime.py` | new, 1,030 lines (777 of code) |
| `runtime.c` | −328 lines of code. It keeps prototypes for the moved functions, the format dispatcher and `pys_fmt_float`. |
| `tools/rt_cpython/_rt.py`, `tools/rtcheck.py` | CPython's primitives and the differential fuzzer |
| `tools/rtabi.py` | the ABI check across `runtime.py`, runtime.c and the corpus |
| `tools/rtbench.py`, `tools/rtbench/` | the microbenchmarks of §2.4.2, for any two compilers |
| `Makefile`, `tests/verify.sh` | the runtime fixed point, the Python-free check, the `rtcheck` and `rt-abi` steps, dictprobe's link |
| `tools/dictprobe.c` | its usage note: the build links `runtime.py`'s IR |
| `README.md` | `runtime.py` in the file table, the pipeline, the bootstrap and the verification steps |
| `tests/rt_format_*` | the format fixes' regression tests (five programs) |
| `docs/runtime-inventory.tsv` | the per-function inventory behind §1.7 |

## Appendix B: reproducing the measurements

- **Correctness.**
  - `make` checks both fixed points.
  - `make verify` runs every step: bootstrap, the tests with both compilers, Python-free, UBSan, check-ir, gc-stress, benchmarks, rtcheck, rt-abi, dict-probes and scaling.
  - `make irsame REF=30b51d9` reports 615 programs identical.
- **Timings.** Every program is run with the native compiler of `30b51d9` and with this branch's, AOT and JIT, best of 7 runs, with its output checked against CPython's.
  - The `bench/` table uses `bench/*.py`.
  - The microbenchmarks are `tools/rtbench/*.py`. `make ref REF=30b51d9 && python3 tools/rtbench.py build/ref/pystachy ./pystachy` reruns the table of §2.4.2 for any pair of compilers.
  - They are small loops over the moved functions, for example:

    ```python
    import sys
    k = len(sys.argv)
    xs = [w * k for w in ["prefix_a", "prefix_b", "other", "pre", "prefix"]]
    n = 0
    for i in range(50000000):
        if xs[i % 5].startswith("prefix"):
            n += 1
    print(n)
    ```

    The `* k` keeps LLVM from folding the loop over constant strings.
- **The probes of §2.4.3** (`ord(s[i])` loops, `list[str]` builders, the insertion sort) are the ABI and codegen probes made for this evaluation. Each was written twice, in the subset and in C over runtime.c, with the same algorithm, and built with `pystachy build` and `clang -O2`.
- **Not in the repository.** These probes, the dict prototype of §1.7 and the callgrind profile of §2.4.1 were made for this evaluation, and only their numbers are reported here. The inventory itself is `docs/runtime-inventory.tsv`.
