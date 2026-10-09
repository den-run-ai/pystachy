# Writing the runtime in the subset

This document evaluates moving `runtime.c`, and the repository's other C code (`tools/dictprobe.c`), into the Pystachy subset itself. It reports on a working prototype, measures it, and compares the approach with how other compilers and runtimes (Go, Rust, Zig, LLVM, Mojo, RPython, Codon and others) write their runtimes in their own languages.

It covers robustness, quality, compilation, performance, scalability, extensibility, code reuse, and the interaction with the two pieces of work in progress: the typed IR (`docs/typed-ir.md`, branch `claude/typed-ir-prep`) and the bug fixes of `claude/m0-correctness` and `claude/scalability`.

The prototype is stacked on `claude/typed-ir-prep` (commit `30b51d9`). Unless a section says otherwise, measurements were made on a 4-core x86-64 VM with LLVM 18.1.3 and CPython 3.13, as the README's are.

## Summary

- **Verdict: promising, as an incremental mechanism, not as a rewrite.**
  - The C runtime gets a second half, `runtime.py`, written in the subset and compiled by the compiler itself.
  - Functions move into it one at a time, keeping their C names and types. Programs call them exactly as before, so **no program's IR changes**: `make irsame` against `30b51d9` reports all 615 corpus programs identical.
  - The garbage collector, the memory layouts of lists, dicts and strings, files and signals stay in C. Every system surveyed in §3 keeps a native core of this kind.
- **What moved in the prototype:** 52 of runtime.c's functions.
  - the `math` module's integer functions (6);
  - the 41 str methods, from `find` to `splitlines`, with `join`, `split` and `rsplit`;
  - the dict hash functions (2), which runtime.c's dict code calls on every lookup;
  - the format-spec mini-language (3), with runtime.c keeping a 7-line dispatcher and the `snprintf` calls that write a float's digits.

  runtime.c loses 328 lines of code (2,470 → 2,142, comments and blank lines aside); `runtime.py` has 724 (956 with comments). The compiler gains 196 lines.
- **How.** `pystachy rt runtime.py` compiles the file in a *runtime mode*:
  - functions named `pys_*` are defined under their C names, with runtime.c's types;
  - `def f(...) -> T: ...` declares a C function;
  - `import _rt` gives 16 primitives, each a few LLVM instructions with their checks: byte reads, an in-place string builder, `memchr`/`memcmp`, wrapping and unsigned arithmetic (§1.2).

  The driver links the result to runtime.c's bitcode in the cached runtime (`build/runtime.bc` and `runtime.o`), so the JIT and AOT tiers both use it, and LLVM inlines across the two languages.
- **Performance: the same as runtime.c on real workloads** (§2.4).
  - The eight programs of `bench/` run at 0.95 to 1.08 times the C runtime's time, and the compiler compiles itself within 3% of it.
  - On 15 microbenchmarks of the moved functions, the median ratio is 1.09 (AOT) and 1.05 (JIT). The range runs from 0.05 (a `find` that `memchr` speeds up 20-fold) to 1.32 (`join`).
  - Without the primitives, the same code is 2.4 to about 20 times slower (§2.4.3).
- **What it buys.**
  - **Testing on CPython.** `runtime.py` is ordinary Python. `tools/rtcheck.py` runs it on CPython against CPython's own str methods, `math` and `format()`: 261,000 cases in about one second, with no compilation. On its first run it found a bug that runtime.c had: the wrong error message for a repeated `,` or `_` in a format spec (§2.2). It is fixed here.
  - **Five more pre-existing bugs**, outside the moved code, turned up during the evaluation and are reproduced in §2.2:
    - undefined behaviour in integer division;
    - a stale length in list `==`;
    - two lax UTF-8 decoders;
    - class ids that overflow their three digits.
  - **Safety by default.** Ported code gets checked arithmetic and checked indexing. Two of the three overflow bugs that runtime.c's history records (commit `452f29c`) are in moved functions, and the subset would have raised `OverflowError` for both. The moved code no longer uses fixed-size buffers.
  - **The roadmap's runtime code in Python.** The open issues imply about 9k to 18k lines of new runtime code, 3.5 to 7 times today's runtime.c (§2.5). Under the current architecture all of it would be C.
  - **Reuse.** The planned WebAssembly GC backend needs a runtime written in the subset (`docs/typed-ir.md` §7.3), and the typed IR's effects table can be inferred from it.
- **What it costs.**
  - A small private dialect (`_rt`) that must stay small and lowerable to every backend.
  - UBSan no longer covers the moved code; the subset's own checks replace it.
  - The runtime is now compiler output: a code generation bug can miscompile it. The bootstrap fixed point now covers `runtime.py`'s IR, and `rtcheck` tests it independently of the compiler.
  - The code is longer: 2.2 times the lines and 1.3 times the characters of the C it replaces.
- **Sequencing.** Keep the runtime ABI frozen while the typed IR's steps 4 to 15 run. Leaf functions can move now, because the move does not change programs' IR. Generic helpers (`pys_eq`, `pys_repr`, the sort) should move after typed-IR step 13, as templates.

## 1. The prototype

### 1.1 runtime.py and runtime mode

`runtime.py` sits next to `runtime.c`. The compiler compiles it as it compiles a program, with these differences (`Gen.rtmode`):

| | program | `runtime.py` |
|---|---|---|
| a top-level `def pys_x` | `define internal ... @f.pys_x` | `define ... @pys_x`, exported under its C name |
| `def f(...) -> T: ...` | rejected (Ellipsis) | `declare T @f(...)`: a function of runtime.c or libc |
| module-level code | runs in `@main.init` | only functions, imports and docstrings: nothing runs it |
| classes | allowed | rejected for now (§5) |
| `import _rt` | `module '_rt' is not supported` | the primitives of §1.2 |
| `@main`, `@pys.roots`, `pys_obj_*` | emitted | not emitted: each program defines them |
| `for i in range(...)`, step ±1 | checked increment | `add nsw` (§2.4.2) |

Two rules keep the ABI right:
- An exported or external function may not take or return `bool`. The runtime ABI passes bools as `i64` (`rtt`), and a `bool` would compile to `i1`. That mismatch links without a warning and is undefined behaviour.
- A function may not use the operation it implements. `math.gcd()` inside `pys_m_gcd` would lower to a call to `pys_m_gcd`. `Gen.rt` reports it at compile time. This is the recursion that other runtimes keep running into (§3: Rust's `memcpy` built from `mem::swap`, Zig's `strlen`).

runtime.c keeps a prototype of every moved function, so its own code can still call them: `hsh()` calls `pys_hash_str`, and `pys_format` calls `pys_format_int`.

### 1.2 The primitives

`import _rt` exists only while `runtime.py` compiles (`RTL` in `pystachy.py`). Each primitive lowers to a few LLVM instructions. Each one checks its arguments, except the arithmetic ones, whose results are defined for every input.

| primitive | meaning | LLVM | Wasm GC (§2.7) |
|---|---|---|---|
| `byte(s, i)` | byte `i` of `s`; `IndexError` outside `0 <= i < len(s)` | one unsigned compare, `load i8` | `array.get_u` |
| `str_new(n)` | a new zeroed str of `n` bytes | `pys_alloc_atomic`, store the length | `array.new_default` |
| `str_put(s, i, c)` | set byte `i` of a str that `str_new` made | compare, `store i8` | `array.set` |
| `copy(d, at, s, lo, n)` | `d[at:at+n] = s[lo:lo+n]` | five compares, `memmove` | `array.copy` |
| `str_done(s)` | hand the str out; it is no longer changed | nothing | nothing |
| `same(a, i, b, j, n)` | `a[i:i+n] == b[j:j+n]` | `memcmp` | a loop |
| `find_byte(s, c, st, en)` | first index of byte `c` (0 to 255) in `s[st:en]`, or -1 | `memchr` | a loop |
| `null(s)` | the null that callers pass for an omitted `str` argument | `icmp eq ptr` | `ref.is_null` |
| `wrap_add/sub/mul(a, b)` | 64-bit arithmetic that wraps | `add`/`sub`/`mul` | `i64.add`/... |
| `shl(a, n)`, `lshr(a, n)` | shifts by `n % 64`, logical to the right | `shl`/`lshr` | `i64.shl`/`i64.shr_u` |
| `udiv(a, b)`, `urem(a, b)` | unsigned division of 64-bit patterns | `udiv`/`urem` | `i64.div_u`/`rem_u` |
| `mul_ovf(a, b)` | whether `a * b` overflows | `smul.with.overflow` | a 128-bit check |

The string length loads and byte accesses that the primitives emit carry TBAA tags: a str's length and its bytes never alias. That lets LLVM keep the lengths in registers in a loop that builds a str, and vectorize it (§2.4.2).

There are no raw pointers and no pointer arithmetic. Every primitive works on a `str` or an `int`, so `runtime.py` stays lowerable to backends without linear memory (§2.7). The systems research of §3 recommends exactly this.

### 1.3 Calling C

`def pys_fmt_float(m: float, ty: int, prec: int, alt: int) -> str: ...` declares runtime.c's function. That is how the format code gets a float's digits, which runtime.c writes with `snprintf`, as before. The same form can declare a libc function.

### 1.4 Building, caching and the bootstrap

- **The cached runtime.** When the driver rebuilds `build/runtime.bc`, it does the following:
  - it compiles `runtime.c` with clang as before;
  - it compiles `runtime.py` in-process, with the compiler that is running;
  - it links the two with `llvm-link` and optimizes the result once with `opt -O2`. LLVM then inlines runtime.c's helpers into `runtime.py`'s code, and the reverse: `hsh()` gets `pys_hash_int` inlined.

  `runtime.o`, the JIT tier's precompiled runtime, is built from that bitcode, so the JIT tier gets the cross-language inlining too.
- **When the cache is rebuilt.** The cache is rebuilt when `runtime.c`, `runtime.py` or the running compiler is newer than it. The running compiler is its executable, or `pystachy.py` under CPython.
  - Another compiler may compile `runtime.py` differently. A stale cache would otherwise outlive a code generation change.
  - Regenerating the IR on every run would be exact, but costs 18 ms of a 40 ms JIT start.
- **The fixed point.** `make` and `make verify` now also check that the three stages emit the same IR for `runtime.py` (`pystachy rt`): 7,971 lines.
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
| format, for int, bool, float and str | `format()` on random specs, some of them malformed. runtime.c's `pys_fmt_float` is replaced by CPython's own float formatting, which is what it reproduces. |

- A default run makes 261,538 comparisons in about one second. It is a step of `make verify`.
- **Mutation check.** Eight bugs planted in `runtime.py` were all detected. They covered whitespace, centering, overlapping `count`, case mapping, `maxsplit`, line breaks, `rfind`'s start and the sign of `gcd`.
- **What it does not test.** 64-bit overflow, because CPython's ints grow. The differential tests compile the same code and check that.

### 1.6 What moved, and what stays in C

| area of runtime.c | moved | stays in C, and why |
|---|---|---|
| strings | 41 methods | `pys_str` (allocation), `pys_str_get`/`slice`/`add`/`mul` (the compiler's lowering of `s[i]`, `s[a:b]`, `+`, `*`), `pys_str_eq`/`cmp`, `pys_ord`/`pys_chr`, repr and ascii escapes, `pys_str_float` (float repr through `snprintf`/`strtod`) |
| arithmetic | `math` gcd, lcm, isqrt, factorial, comb, perm | the operators the compiler lowers to (`//`, `%`, `**`, shifts), `pow(a, b, m)` (128-bit), the libm wrappers |
| repr, `==`, ordering | none | generic helpers that interpret type descriptors at run time and call back into the program. They should become templates (§2.8). |
| lists and timsort | `join`, `split`, `rsplit`, `splitlines` | list memory, and timsort (a list bounds check blocks `memmove` recognition: §2.4.3) |
| dicts | the two hash functions | the table itself: raw `int32` index arrays and `uint64` hash arrays |
| formatting | the format-spec mini-language | the dispatch on the descriptor, and float digits (`snprintf`) |
| I/O, process, signals, time, errno, tempfile | none | stdio, `errno`, signal handlers, system calls |
| the collector | none | stack and register scanning, the page map, raw memory |

## 2. Evaluation

### 2.1 Robustness

**Better.**
- **Checked by default.** In `runtime.py`, `+`, `-` and `*` raise `OverflowError`, and the primitives check their indexes.
  - **Evidence from runtime.c's history.** Commit `452f29c` fixed three integer overflows in runtime.c that review had found. Two of them are in functions moved here:
    - `math.lcm` negated a product of -2**63 and returned -2**63;
    - `str.split` counted a negative `maxsplit` down past -2**63.

    In the subset, both raise `OverflowError` at the faulty operation, with no hand-written test. Only the documented 64-bit deviation remains.
  - The C code had to test for overflow by hand, and the tests were sometimes missing. For example, `pys_str_join` summed its parts' lengths unchecked. That sum cannot overflow in practice, but nothing in the code says so. In `runtime.py`, the check is there by default.
  - runtime.c's `comb` needed `unsigned __int128` to stay exact. `runtime.py` multiplies directly unless `mul_ovf` says the product would overflow, and otherwise reduces by a gcd first. No step overflows unless the result does.
- **Fixed buffers are gone** from the moved code: the format code's `char r[70]` digit buffer and its `failf` buffer of 512 bytes. They were sized correctly, but nothing checked that. The float digits keep their C buffer, inside `pys_fmt_float`.
- **The bug found by testing on CPython** (§2.2) is a robustness gain of its own: errors are now reported the way CPython reports them.

**Worse, or different.**
- **UBSan.** `make verify`'s UBSan stage instruments C only. `clang -fsanitize=undefined` adds no checks to `.ll` input, so it no longer covers the moved code.
  - The moved code cannot have the undefined behaviour UBSan looks for. Its arithmetic is checked or explicitly wrapping, and its memory accesses go through checked primitives.
  - The remaining risk is a bug in a primitive's lowering, which is about 75 lines of `Gen.primitive`.
- **A compiler bug can now break the runtime.** Before, a code generation bug miscompiled programs; now it can also miscompile the runtime they link. Three things contain it:
  - the fixed point covers `runtime.py`'s IR;
  - `rtcheck` tests the same code without the compiler;
  - the differential tests run every program against CPython.
- **Errors raised inside runtime code.** A primitive's check (for example `IndexError: string index out of range` from `byte`) would surface as the program's error. That is better than a wild read, but it names nothing in the program. None of the tests triggers one: a check that fires means a runtime bug.

### 2.2 Quality and testability

- **One language for the semantics.** The moved functions now read like the CPython behaviour they implement. `pys_str_count` is a loop over `search()` instead of `memmem` pointer arithmetic.
- **Differential testing in-process.** `rtcheck` is the RPython idea (§3): run the runtime on the host interpreter.
  - It compares about 300,000 cases per second against CPython itself (261,538 in 0.85 s). The differential test suite compiles each program twice and runs it.
  - On its first run, its format fuzzer found that runtime.c reported `Cannot specify both ',' and '_'.` for `f"{x:,,}"` and `f"{x:__}"`. CPython reads `,` and then `_`, so a second `,` or `_` is taken as the presentation type: `Cannot specify ',' with ','.`
  - The fix is three lines of `runtime.py`. `tests/rt_format_comma_twice.py` and `tests/rt_format_underscore_twice.py` were recorded from CPython; the compiler of `30b51d9` fails both.
- **Another bug found during this evaluation**, outside the runtime: class ids in type descriptors are written with `{:03d}` and read as exactly three digits (`ocls` in runtime.c). With more than 1,000 classes in containers, `repr([C1000()])` calls `C100.__repr__`.
  - The repro is 1,002 classes, each put in a list and printed. It prints `[C100]` where CPython prints `[C1000]`.
  - It is not fixed here, because the fix changes descriptors in programs' IR.
- **Two more bugs, in code not moved yet.** runtime.c has three UTF-8 decoders. The strict one is `u8char`. The lax copies in `pys_ascii` and `asciinum` accept overlong forms and code points above U+10FFFF:
  - `ascii(chr(0xC1) + chr(0xBF))` prints `'\x7f'`, where CPython prints `'\xc1\xbf'`;
  - `int(chr(0xE0) + chr(0x99) + chr(0xA0) + "7")` returns 7, reading the overlong bytes as U+0660 ARABIC-INDIC ZERO, where CPython raises `ValueError`.

  Both were reproduced with the compiler of `30b51d9`. One decoder in `runtime.py`, tested on CPython, would fix them by construction. `int()`, `float()` and `ascii()` are next on the list (§5).
- **Two more, of the kind the subset rules out.** Both were reproduced with the compiler of `30b51d9`.
  - **Undefined behaviour in `pys_idiv`.** It calls `__builtin_clzll(0)` when the dividend is 0 and the divisor is above 2**53. With UBSan, `k / (1 << 60)` for `k == 0` aborts: "passing zero to clz(), which is not a valid argument". Without it, the result is right by luck. No test reaches it, so `make verify`'s UBSan step did not see it.
  - **A stale length in list `==`.** `eqv` compares the two lengths once, then reads both lists' slots. If an `__eq__` empties the other list, it reads zeroed slots and passes a null object to the next `__eq__`. The program dies with `AttributeError: 'NoneType' object has no attribute 'v'` where CPython prints `False`.

  In `runtime.py`, the first cannot happen: there is no undefined arithmetic. The second would be an `IndexError` from a checked read, not a null object; a faithful port re-reads the lengths, as CPython's `list_richcompare` does.
- **Review.** A change to a moved function is a change to Python code that `rtcheck` exercises in a second. A change to runtime.c needs the full test suite and a sanitizer build.

### 2.3 Compilation and bootstrap

| | `30b51d9` (C runtime) | prototype |
|---|---:|---:|
| `make verify`'s bootstrap step (both fixed points for the prototype) | — | 24.6 s |
| cold runtime build (`build/runtime.bc` and `.o`), plus hello world | 1.87 s | 2.15 s |
| `runtime.py` to IR | — | 18 ms native, 0.23 s under CPython |
| hello world, JIT, warm cache | 34.1 ms | 33.7 ms |
| AOT build of `bench/words.py` | 0.409 s | 0.426 s |
| compiler compiling `30b51d9`'s `pystachy.py` to IR | 0.167 s | 0.172 s |
| `build/runtime.bc` / `runtime.o` | 202 KB / 201 KB | 252 KB / 210 KB |
| hello world, AOT executable | 24,008 B | 24,008 B |
| native compiler | 1,007,040 B | 1,040,400 B |

- A cold runtime build costs 0.28 s more: `runtime.py`'s IR, `llvm-link`, and one `opt -O2` over the linked module. A warm cache costs nothing: the JIT tier's startup is unchanged.
- `runtime.bc` grows by 25% because it holds `runtime.py`'s code before `--only-needed` linking. The JIT tier's `runtime.o` grows by 4%, and an AOT executable does not grow.
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

- **Where the subset wins.** `find` with a rare first byte runs 20 times faster. `search()` looks for the needle's first byte with `memchr` (AVX2 in glibc), where runtime.c called `memmem`, whose two-way algorithm is slower when matches are sparse. This is a best case. With dense matches (`count_ab`), the inline 16-byte scan keeps the cost within 9% of `memmem`.
- **Where it loses.**
  - `join` (1.32) pays five bounds checks and a `memmove` per part, where C has an unchecked `memcpy`.
  - `strip` (1.18) tests the `null` default for each byte.
  - `comb` (1.23) pays the `mul_ovf` test in its loop.
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
  - M5: an error flag at 135 failure sites;
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
  - Code that needs raw memory (the collector, list and dict tables) or generic slots (the descriptor-driven `eq`/`repr`/sort) is not. That needs either templates (typed IR §7.3) or a pointer layer, which §5 argues against for now.
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
  - The prototype edits `Gen.rt`, `Gen.function`, `Gen.declare_fn`, `Gen.program`, `for_range` and the driver. The IR steps rewrite all of these.
  - The edits are small: 196 lines, most of them in `primitive()` and the driver. They would move into the lowering with the code around them.
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
  - On the stack, 8 of 78 commits touched runtime.c, mostly adding functions at the end of sections.
  - The functions moved here were last changed on `claude/modules-and-templates` (`pad`, the split helpers) and `claude/scalability` (`hsh`). The prototype is stacked on both.
- **Coordination.** Future fixes to a moved function go to `runtime.py`, with a regression case in `rtcheck` where CPython can serve as the reference. This applies to the sessions working from #4, #13–#17 and the M-issues.
- **Where conflicts will come from.** The dict core (typed-IR §7.1's fused lookups, M1, M4, M7's sets) and M5's error paths, which touch every `pys_fail`. Neither is moved here.
- **Fixes get cheaper.** The separator bug of §2.2 is one example: the fuzzer found it, the fix is three lines of Python, and `rtcheck` confirms it in a second.

## 3. How other compilers and runtimes do it

| system | in the language | still native | low-level dialect | how it moved | measured effect | how it is tested |
|---|---|---|---|---|---|---|
| **Go** (1.4–1.5, 2014–15) | the runtime and GC: 122k lines of Go in `src/runtime` | per-arch assembly (8.5k lines for amd64, all OSes), cgo C | `unsafe.Pointer`; `//go:nosplit` (1,032 uses), `//go:linkname` (787), `nowritebarrier`; the runtime is compiled with `-+`, where a heap escape is an error | a C-to-Go translator, then hand edits, over 20 months; checked by bit-identical compiler output | Go 1.4: precise GC, heap 10–30% smaller, the runtime "slightly" faster thanks to the Go compiler's inlining. Go 1.5: builds 2× slower; the translated compiler started 10× slower | as an ordinary package (`export_test.go`), with GODEBUG stress modes |
| **Rust** | `core`, `alloc`, `std`, `compiler-builtins` (a port of compiler-rt, 8.8k lines) | an optional C fallback for builtins, libunwind | intrinsics, lang items, `no_std`, `#![no_builtins]` | one intrinsic at a time, with the C version as a fallback; 10 years on, still not complete | no aggregate study; builtins are kept out of LTO | against the host's compiler-rt/libgcc, and MPFR for libm |
| **Zig** | `compiler_rt` (23k lines plus 97k of tests, no C), libc functions moving into libzigc | about 2,000 bundled C files (Jan 2026) | `export`, weak/hidden symbols, `no_builtin`, `no_panic` | function by function, deleting each C copy | shipping the runtime as source, built lazily per target, is what makes cross-compiling work; the self-hosted compiler builds in a third of the memory | tests ported with each routine |
| **LLVM libc** | libc in C++ (326k lines) | 48 files with inline asm | `LIBC_INLINE`, no dependency between public entry points | new code, used beside the system libc | correctly rounded math; GPU builds ship bitcode for LTO | MPFR, exhaustive single-precision tests, differential fuzzing against the system libc |
| **Mojo** | the standard library (116k lines) | CompilerRT (1.2k lines of C++), AsyncRT (12k) | `__mlir_op` (256 uses), `__mlir_type`, `@always_inline("builtin")` | written in Mojo from the start | library-defined `Int.add` stopped compile-time folding until a "builtin" inlining was added | the stdlib's own tests |
| **RPython / PyPy** | the GC (incminimark, 3.5k lines; 15.8k for the memory layer) and the interpreter, in a Python subset | 10.9k lines of C support (dtoa, threads, signals) | `lltype`, `llmemory`, `llarena`, `llop` | designed that way | a full translation takes 20 to 45 minutes and 4 to 6 GB | **untranslated, on CPython**: the model for `rtcheck` |
| **Codon** (a Python-syntax LLVM compiler: the closest analog) | the standard library, `int`, `str`, `list` and `dict` included: 94k lines | 1.7k lines of C++ (allocation, print, locale, exceptions, regex) and the Boehm GC | `@llvm` functions with inline LLVM IR (758 of them), `Ptr[T]`, `@C` | written that way from the start | "rival C/C++ in performance" (CC'23); the library is tied to LLVM text | its own test suite |
| **Jikes RVM / MMTk** | the whole JVM, GC included, in Java | a small boot loader | `org.vmmagic`: unboxed `Address`/`Word`, intrinsics, `@Uninterruptible` | — | MMTk in Java (2004): about 5% slower than monolithic collectors, 60% faster than glibc's malloc thanks to inlining. Its "fully-static dialect of Java" blocked reuse, and it was rewritten in Rust in 2016. | a harness that simulates memory as a hash table of pages |
| **GraalVM Native Image** | the serial GC (25k lines of Java) | 3.9k lines of C helpers | `org.graalvm.word`, `@Uninterruptible` (711 uses in the GC) | — | "the object layout code used by the GC can immediately be used in other parts of the VM and the compiler" | runs hosted on HotSpot, with boxed words |
| **Nim** | `system`, the ARC/ORC memory management, the allocator, and a conservative refc GC: 19k lines | 1.1k lines of C headers | `cast`, `ptr`, `{.compilerRtl.}`, `{.push rangeChecks: off.}` | ORC became the default in 2.0 (2023) | ORC: 320 µs average latency against 65 ms for mark-and-sweep under forced collections | Valgrind and sanitizers |
| **Swift, Julia** | the standard library (150k lines), `Base` (139k) | the runtime and GC in C/C++ (50k lines; 152k) | the `Builtin` module; `Core.Intrinsics`, `llvmcall` | — | Julia's C runtime hides roots, which made a moving GC impractical "on a code base with hundreds of thousands of lines" | — |
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
4. **The recurring bug is the compiler creating a call into the runtime from the runtime itself**: Rust's `mem::swap` becoming `memcpy`, Zig's LLVM 21 `strlen`, LTO's `memcmp` to `bcmp`. `Gen.rt` rejects the compiler's own version of this. LLVM may still turn byte loops into `memcmp`/`memchr`/`strlen` calls, which go to libc, not to the runtime.
5. **The move is incremental, with both versions kept checkable**: Rust's C fallback, Zig's per-function deletions, Go's bit-identical output. Here the C version stays in git history, and `make irsame REF=30b51d9` and the differential tests compare against it.
6. **The payoff that has actually been measured is not raw speed.** It is precision and memory (Go's GC), tooling and portability (Zig), inlining across the old language boundary (MMTk, Go), and testing on a host (RPython, MMTk's harness, GraalVM's hosted mode). The prototype matches runtime.c's speed (§2.4); its gains are testing, safety and the backends.
7. **The library part moves first, and the GC last or never.** Codon (Boehm), Swift, Julia and Kotlin/Native keep their collectors native. The collector is written in the language itself only where there is a compiler-checked low-level regime: a no-allocation rule, `Address`/`Word` types and a simulated-memory test mode (RPython, vmmagic, SubstrateVM, Go, Slang). Pystachy has none of these yet. This is why §5 keeps the collector in C.
8. **Wasm GC forces the move.** Every Wasm GC compiler surveyed wrote its runtime in its source language over Wasm-instruction intrinsics, and none ported a collector, because the engine has one.
9. **The runtime dialect should stay a subset of the language, not a separate one.** MMTk's restricted Java cut the collector off from libraries and other hosts. Slang dropped objects altogether. RPython is remembered for "cryptic" errors. `runtime.py` is ordinary subset code, with the subset's error messages, that CPython also runs. That last property keeps Pystachy's bootstrap CPython-only: inline LLVM text, as in Codon's `@llvm`, would end it.

## 4. Risks and how the prototype handles them

| risk | handling |
|---|---|
| a code generation bug miscompiles the runtime | fixed point over `runtime.py`'s IR; `rtcheck` runs the same code on CPython, without the compiler; differential tests |
| a stale cached runtime after a compiler change | the cache is rebuilt when the running compiler is newer (§1.4) |
| ABI mismatch between `runtime.py` and the program's declarations | no `bool` in exported or external signatures; `make verify`'s `rt-abi` step (`tools/rtabi.py`) requires one LLVM signature per function across `runtime.py`, runtime.c and the 297 programs of the corpus (1,083 uses), and reports a planted mismatch |
| self-recursion through a lowering | rejected at compile time (`Gen.rt`) |
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
| a full port, collector included, with a pointer layer (RPython's `llmemory`) | A large `_rt` that cannot lower to Wasm GC. The conservative collector scans C stacks and registers either way, so it gains nothing. Every system in §3 keeps such a core native. |
| the runtime as a `lib/` prelude compiled into every program | Every program's IR would change with every runtime edit, which conflicts with `irsame` and the typed IR's migration. The JIT tier would recompile the runtime on every run, or need the same cache. |
| Rust, Zig or C++ for the runtime | A second toolchain, outside the self-hosting and Python-free stages. It removes undefined behaviour but adds no CPython testability and no Wasm GC reuse. |
| a mechanical C-to-subset translator (Go's c2go) | The subset lacks pointers, so most of runtime.c would not translate. Go's translator also needed the C refactored first and produced "unidiomatic Go code that performs poorly". The leaf code that does translate is small enough to port by hand, and hand ports came out at C's speed. |
| inline LLVM IR in runtime functions (Codon's `@llvm`, Julia's `llvmcall`) | It binds the runtime to one backend's text, so the Wasm GC backend could not reuse it. CPython could no longer run `runtime.py`, which would lose `rtcheck` and the CPython-only bootstrap. `_rt`'s primitives are operations each backend lowers, as Julia's intrinsics and Mojo's `pop` dialect are. |

## Appendix A: what the prototype changes

| file | change |
|---|---|
| `pystachy.py` | +196/−8 lines:<br>• runtime mode (`rtmode`, exported and external functions, `RTL` and `primitive()`, nsw range steps);<br>• `pystachy rt`;<br>• the driver's runtime build and cache rule |
| `runtime.py` | new, 956 lines (724 of code) |
| `runtime.c` | −328 lines of code. It keeps prototypes for the moved functions, the format dispatcher and `pys_fmt_float`. |
| `tools/rt_cpython/_rt.py`, `tools/rtcheck.py` | CPython's primitives and the differential fuzzer |
| `tools/rtabi.py` | the ABI check across `runtime.py`, runtime.c and the corpus |
| `tools/rtbench.py`, `tools/rtbench/` | the microbenchmarks of §2.4.2, for any two compilers |
| `Makefile`, `tests/verify.sh` | the runtime fixed point, the Python-free check, the `rtcheck` and `rt-abi` steps, dictprobe's link |
| `tools/dictprobe.c` | its usage note: the build links `runtime.py`'s IR |
| `README.md` | `runtime.py` in the file table, the pipeline, the bootstrap and the verification steps |
| `tests/rt_format_*_twice.*` | the separator bug's regression tests |

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
