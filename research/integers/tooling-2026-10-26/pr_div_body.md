## Problem and change

After #903 and #904, long division was the largest remaining gap in the `mpz` core. #901's `bench/integers/bigmul` (products of ~6,000-digit values, then `//` and `%` by a 2,500-digit modulus) still ran at 0.59× CPython's speed. Division was MicroPython's `mpn_div`:

- It estimated each quotient digit from the dividend's top two digits and the divisor's top 30 bits, then corrected the estimate by repeated add-back.
- It renormalized every divisor digit inside its inner loop.
- One-digit divisors took the same path.

This PR follows CPython 3.13.16's `Objects/longobject.c`:

| CPython function | Now in `mpz/mpz.c` |
|---|---|
| `x_divrem` (Knuth 4.3.1, Algorithm D) | Shift both operands once so the divisor's top digit has its high bit set. Estimate each quotient digit from two dividend digits and correct it with the divisor's second digit. Fix it with at most one add-back |
| `divrem1` | A one-digit divisor divides digit by digit |

The loops stay indexed, so they never form a pointer before an array. Python's floor rules, zero-division messages and the sharing rules for immutable results are unchanged. After this, the multiply-add is the only MicroPython-derived code. The default integer path is untouched. Refs #12.

### Measurements

The core was timed without the class wrapper or collector: `clang -O2`, CPU-pinned, best of 7. It was compared with `timeit` on the pinned CPython 3.13.16 on the same shared 4-vCPU Xeon VM:

| Operation | Before | After | CPython |
|---|---:|---:|---:|
| 4,200 digits // 1,401 digits | 87.7 µs | 69.5 µs | 70.3 µs |
| 4,200 digits % 1,401 digits | 88.4 µs | 69.2 µs | 69.9 µs |
| 640 digits // 214 digits | 3.10 µs | 2.16 µs | 2.23 µs |
| 160 digits // 54 digits | 0.28 µs | 0.23 µs | 0.25 µs |
| 4,200 digits // 1000000007 | 4.58 µs | 2.97 µs | 3.03 µs |
| 4,200 digits // 4,200 digits | 1.54 µs | 1.92 µs | 2.10 µs |

Equal-length operands, whose quotient has one digit, are slower than before: both operands are now shifted up front. They remain faster than CPython.

End to end, #901's `bench/integers` mpz programs were built AOT against each runtime: medians of 7 interleaved, pinned runs, the same checksum as CPython. Speeds relative to CPython 3.13.16:

| Workload | main before #903 | after #904 | this PR |
|---|---:|---:|---:|
| `bigmul` | 0.53× | 0.59× | 0.97× |
| `modpow` | 0.69× | 0.72× | 0.84× |
| `containers` | 0.59× | 0.65× | 0.69× |
| `dectext` | 0.30× | 0.91× | 0.90× |
| `cross64` | 0.82× | 0.96× | 0.97× |

## Validation

Local, Linux x86-64, LLVM 18.1.3, CPython 3.13.16. The tree of `72b57dc` is identical to the locally tested commit (`233f6b7a` tree):

- **Build:** `make` reached the three-stage fixed point.
- **Corpus:** every mpz program, `mpz_shadow`, the mpz rejections and `upstream_int_*.py` pass in JIT and AOT (41/41).
- **Stress, sanitizers, optimizations off:** `PYSTACHY_GC_STRESS_PROGRAM=1` passes 28/28; a UBSan runtime passes 14/14 AOT and 14/14 JIT; `PYSTACHY_OPT=-all` passes 28/28.
- **New regression:** `mpz_division.py` divides with:
  - divisors whose top digit has every bit length 1–30 (every normalization shift), at 1–75 digits;
  - quotients of 1 bit to 450 bits;
  - remainders of 0, the divisor minus one, and a random one;
  - every sign combination (9,000 checks);
  - quotient digits of 2^30 − 1 with all-ones divisors (the add-back step);
  - dividends below or equal to the divisor.

  Each check is `q * b + r == a` with Python's remainder bounds, and CPython checks the printed digests. With a collection at every allocation it takes 0.49 s.
- **Adapted CPython cases:** #902's `mpz_cpython_long_division.py` (900 `getran()` pairs) and #889's `mpz_cpython_long.py` (the twelve fixed `test_division` corner cases, including quotient-digit estimates of `BASE + 1` and the post-subtraction correction) pass unchanged.
- **Differential C harness** (scratch, not committed), built with GCC `-fsanitize=address,undefined`:
  - About 107,000 checks of the new core against main's.
  - 12,000 targeted divisions (every normalization shift, one-digit divisors, all-ones quotients, add-back cases, every sign) and 1,500 mixed large operations compared with CPython's `int`.
  - All identical, with no sanitizer reports.
- **Checks:** `make lint`, `make check-runtime`, `make check-recordings` (1,725 recordings, 0 failed), `make check-repository` and `git diff --check` pass.

CI on `72b57dc`: all 37 checks passed, including the aggregate `make verify`; the fork-only DCO check was skipped.

## Risks and provenance

- **License:** adapted from CPython 3.13.16's `Objects/longobject.c` (PSF License v2), as `THIRD_PARTY_NOTICES` (both copies) and `mpz/README.md` record, with the source hash from #903. The MicroPython MIT notice stays for the multiply-add.
- **Remaining gaps:** division stays quadratic, as CPython's is below its `_pylong` thresholds; the API has no `divmod`, so `x // y` and `x % y` each divide.
- **AI assistance:** Claude Code wrote the change, the harness and the tests, ran the validation and drafted this description at the maintainer's request. No independent review is implied.

## Checklist

- [x] I reviewed and can explain the complete change.
- [x] I added regression coverage, or explained why it is not applicable.
- [x] The diff contains no raw research, transient handoffs or unapplied prototype patches; reusable checks and fixtures are in maintained locations.
- [x] I have the right to contribute this work and preserved applicable license notices.
- [x] For a PR from a fork: not applicable (branch of this repository).
