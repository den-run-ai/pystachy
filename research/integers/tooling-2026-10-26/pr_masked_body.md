## Problem and change

`int` is checked 64-bit, so `(k * 0xCC9E2D51) & 0xFFFFFFFF` raised `OverflowError` once the product passed 2^63, although the masked result fits (#125). MurmurHash3, FNV-1a, djb2, xorshift and `java.util.Random`'s LCG are written this way.

This implements part 1 of #125's suggested fix ("masked arithmetic, now"), following its prototype:

- In `x & y` where a side is a tree of `+`, `-`, `*` and `<<` (also under `&`, `|` and `^`), that side is computed in wrapping 64-bit arithmetic. A flag records "a step overflowed": the checked operations' overflow bits, and for `<<`, lost bits or a count of 64 or more.
- Those steps keep the exact result's low 64 bits. `x & y` needs no other bits where the other side is exact and not negative, so the result is CPython's.
- Otherwise `OverflowError` is raised, as the overflowing step raised before, but only after the whole expression has been evaluated (see Risks).
- A negative shift count still raises `ValueError` at once. An operand that is not an `int` (a bool, an object, a union, an `Any` box) takes the operator's usual lowering, after any overflow so far.
- In a Dynamic `Any` program, literal operands still fold as `gen_arith` folds them, so the result shares its literal's constant box: `(1000 + 23) & 1000 is 1000`, as in CPython.
- A literal non-negative mask needs no check: `(a + b) & 0xFF` compiles to a wrapping add and an `and`.

The new code raises only where main raised (a step overflowed), and gives main's value wherever no step overflows. It lives in `gen_masked`, `gen_wexpr` and `gen_wflag` (`expressions.py`), called from `gen_expr`'s binop branch. Unsigned 64-bit values (part 3 of #125) still need big integers (#12). Refs #125.

This stays a draft: it changes when an `OverflowError` is raised, and the maintainers should decide whether that is acceptable.

### Results

#125's repros with CPython 3.13.16, main's compiler (unchanged from `e314f08` to `68a67fc`) and this PR. JIT and AOT print the same:

| Program | CPython | main | this PR |
|---|---|---|---|
| `u4_mul32.py` | `506548822` / `2099483743` | `506548822`, then `OverflowError` | as CPython |
| `u3_mask_after.py` | `5863208` / `1157481973763320461` | `5863208`, then `OverflowError` | as CPython |
| `m_edges.py` | 25 lines | `248`, then `OverflowError` | as CPython, except 3 lines |
| `m_bench.py 20000` | `3270003030`, 9.36 s | `OverflowError` | `3270003030`, 0.050 s AOT, 0.044 s JIT |

The 3 lines of `m_edges.py` are `(big * 4) & v` with `v` -16, -1 and `big * 4` itself, where `big = 1 << 62`. CPython prints `18446744073709551616`, which needs more than 64 bits, so this PR raises `OverflowError` there, as #125 specifies. `m_bench.py` times are the loop's CPU seconds: medians of 5 (AOT) or 3 runs, pinned to one core of a shared 4-vCPU VM.

## Validation

Local, Linux x86-64, LLVM 18.1.3, CPython 3.13.16. The first commit was validated as `0a14ee3` (based on `e314f08`; the compiler, `lib/` and `runtime.py` are unchanged on main since):

- **Build:** `make` reached the three-stage fixed point (713,909 compiler and 18,735 runtime IR lines).
- **IR oracle:** `tools/irsame.sh` against `e314f08`'s compiler over 3,674 programs. Both compilers read this checkout's home (`PYSTACHY_HOME`), as `build/ref/lib`, `runtime.c`, `runtime.py` and `mpz/` are identical to it; otherwise every library diagnostic differs by its `build/ref/` prefix (`make irsame` then reports 253 programs, 131 of them only for that prefix). No diagnostic or exit status changes. 122 programs' IR differs. Compared per function, with string constants named by their contents, every changed function holds an `&` over `+`, `-`, `*` or `<<`:
  - `lib/re/_sre.py`: `_span_rest`, `_charset_memo`, `_branch_search`, `_branch_high` (most of the 122 programs import `re`);
  - `lib/_pyrandom.py`: the Mersenne Twister's `_init_genrand`, `_init_by_array`, `_genrand_uint32`, and `_hash_float`;
  - `lib/_pystachy_binascii.py`: `a2b_base64`, `a2b_uu`, `_crc_hqx_table`, `crc_hqx`;
  - `lib/datetime.py`: `_scale_delta`, `_big_shr_round`; `lib/json.py`: `_Parser.key`;
  - the compiler itself (`pystachy.py`): `driver.fnv` and `Lexer.number`;
  - tests: `arith.py`, `bytes_reads.py`, `upstream_math_integer.py` and the two new cases.

  The other differences are string constants renumbered after the new `negative shift count` message, and one `pys_exc_new` declaration.
- **Corpus:** the 117 test programs whose IR differs (all but `pystachy.py` and four benchmarks, which CI's benchmark group runs), with `tests/programs/numbers/*.py`: 177 cases, 354/354 pass in JIT and AOT.
- **Stress, optimizations off, sanitizers:** a focused set of 19 (the new cases, `arith.py`, `bytes_reads.py`, `upstream_math_integer.py`, and the `random`, `binascii`, `json`, `datetime` and `re` programs above) passes 38/38 with `PYSTACHY_GC_STRESS_PROGRAM=1`, 38/38 with `PYSTACHY_OPT=-all`, and with a UBSan runtime 19/19 AOT and 19/19 JIT.
- **Checks:** `make lint`, `make check-ir` (1,905 programs), `make check-runtime`, `make check-fast`, `make check-recordings` (1,723 recordings, 103 deviations, 0 failed) and `git diff --check` pass.

**On current main:** the tree of `b2268ad` (`5caf46aa`, on main `68a67fc`) was tested locally as `0a14ee3` cherry-picked onto `72b57dc`, whose tree #905's merge kept. It reaches the same fixed point, and the mpz programs, `upstream_int_*.py`, the mpz rejections and the focused set above pass in JIT and AOT (42 cases, 77/77).

**Second commit, `623f3fe`:** CI on `b2268ad` passed every check except `verify (dynany-optin-3)` and so the aggregate `make verify`. That group reruns each `tests/programs` case opted in to Dynamic `Any`, and `int_masked.py` raised `OverflowError` there, because the first commit skipped any program with a Dynamic `Any` module. `623f3fe` applies the lowering in those programs too, and keeps their literal folding. Without the folding, three new cases in `dynany_identity_folded_ints.py` print `False` (CPython and main print `True`). Local results on `623f3fe`:

- `make` reached the fixed point (714,052 compiler IR lines).
- `tools/irsame.sh` against `b2268ad`'s compiler (shared home, identical inputs): 9 of 3,677 programs differ, with no diagnostic or exit-status change. All are Dynamic `Any` programs: 5 opt in, and 4 import `tomllib`, whose modules opt in. Every changed function is a masked site listed above (`_span_rest`, `_charset_memo`, `json._Parser.key`, the `_pyrandom` functions).
- `tools/dynany_optin.py` over the 172 affected programs: 344/344 pass in JIT and AOT, including `int_masked.py`. The 8 changed test programs and the identity test pass in JIT and AOT (18/18); the ninth, `bench/pyperformance/json_loads.py`, runs in CI's benchmark group. The identity test's IR is the same as with `b2268ad`'s compiler, whose generic path folded these literals; with `PYSTACHY_GC_STRESS_PROGRAM=1`, the identity test, both new cases, `lib_tomllib_dynamic.py` and `dynany_json.py` pass 10/10.
- `make lint`, `make check-fast`, `make check-ir` (1,908 programs), `make check-runtime`, `make check-recordings` (1,726 recordings, 0 failed) and `git diff --check` pass.

CI on `623f3fe`: all 37 checks passed, including `verify (dynany-optin-3)` and the aggregate `make verify`; the fork-only DCO check was skipped.

## Risks and provenance

- **Later errors:** where the masked result can need more than 64 bits (both sides overflowed, or the other side is negative), `OverflowError` now comes after the whole expression has been evaluated, so a call later in the expression runs first. In `(f(big) * 4) & f(-1)`, main raised before the second call. CPython raises nothing there: it returns a bigger int. `tests/deviations/int_masked_overflow.py` and the compatibility reference record this. Likewise, an error that a later operand raises (a negative shift count, a missing key) now comes before the overflow's, as in CPython.
- **Huge shift counts:** `(x << n) & m` with `n` of 64 or more gives the exact low bits, which are 0. Main raised `OverflowError` there. CPython builds the whole number first, and raises `MemoryError` for counts beyond memory.
- **Conservative flag:** the flag passes through an inner `&`. `(((a * b) & 0xFF) + c) & y` with a negative `y` still raises after `a * b` overflows, although the inner mask made it exact. Main raised there too.
- **Not covered:** augmented `x &= expr` keeps the previous lowering, and `>>`, `//`, `%`, `**` and unary minus inside the tree stay checked. Code that overflows in an assignment before a later mask (`h = h * 31 + c`, then `h &= M`) still raises, as in main.
- **Provenance:** original code following #125's prototype; no third-party source.
- **AI assistance:** Claude Code wrote the change and the tests, ran the validation and drafted this description at the maintainer's request. No independent review is implied.

## Checklist

- [x] I reviewed and can explain the complete change.
- [x] I added regression coverage, or explained why it is not applicable.
- [x] The diff contains no raw research, transient handoffs or unapplied prototype patches; reusable checks and fixtures are in maintained locations.
- [x] I have the right to contribute this work and preserved applicable license notices.
- [x] For a PR from a fork: not applicable (branch of this repository).
