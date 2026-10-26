## Problem and change

`mpz` multiplication (#889) was schoolbook only. A product of two 14,000-bit values took 2.2× as long as CPython's, and squares (`x * x`, `pow`) gained nothing from their symmetry. Addition and subtraction ran one loop with two bounds checks and a subtract flag per digit.

This PR follows CPython 3.13.16's `Objects/longobject.c`, continuing #903:

| CPython function | Now in `mpz/mpz.c` |
|---|---|
| `x_add`, `x_sub` | One loop over the shorter operand's digits, then the carry or borrow through the longer one's |
| `x_mul` | Schoolbook, with HAC 14.16 squaring when both operands are the same value (each cross product added once, doubled) |
| `k_mul` (+ `kmul_split`, `v_iadd`, `v_isub`) | Karatsuba's three half-size products above CPython's cutoff of 70 digits, or 140 for squares |
| `k_lopsided_mul` | An operand at least twice the other's length is multiplied slice by slice, so every split stays balanced |

Temporaries are fresh, unpublished collector allocations held in C locals. The collector scans the C stack and registers conservatively, with interior pointers. Results stay immutable. Division (still MicroPython's) and the default integer path are untouched. Refs #12.

### Measurements

The core was timed without the class wrapper or collector: `clang -O2`, CPU-pinned, best of 7. It was compared with `timeit` on the pinned CPython 3.13.16 on the same shared 4-vCPU Xeon VM:

| Operation | Before | After | CPython |
|---|---:|---:|---:|
| Product, 4,200 × 4,200 digits | 189 µs | 78.6 µs | 85.2 µs |
| Square, 4,200 digits | 186 µs | 61.8 µs | 55.8 µs |
| Product, 4,200 × 1,401 digits (lopsided) | 62.7 µs | 35.9 µs | 40.2 µs |
| Product, 1,000 × 1,000 digits | 10.1 µs | 7.1 µs | 7.8 µs |
| Product, 640 × 640 digits (schoolbook) | 4.0 µs | 2.9 µs | 3.4 µs |
| Square, 640 digits | 4.1 µs | 2.2 µs | 2.0 µs |
| Difference, 4,200 digits | 0.61 µs | 0.46 µs | 0.65 µs |
| Sum, 4,200 digits | 0.45 µs | 0.46 µs | 0.51 µs |

End to end, #901's `bench/integers` mpz programs were built AOT against the old and new runtime (medians of 7 interleaved, pinned runs, same checksums). `bigmul`, `fibadd`, `modpow`, `arith128` and `cross64` take 7–13% less time, and `cross64` reaches CPython's time (0.47 vs 0.45 s). `bigmul` stays at 0.59× of CPython's speed because long division dominates it. A follow-up PR ports CPython's `x_divrem`, which brings it to 0.97× in the same measurement.

## Validation

Local, Linux x86-64, LLVM 18.1.3, CPython 3.13.16. The tree of `4e301f9` is identical to the locally tested commit (`b49fcc16` tree):

- **Build:** `make` reached the three-stage fixed point.
- **Corpus:** all 12 mpz programs (including the new `mpz_multiplication.py`) pass in JIT and AOT (24/24), and under `PYSTACHY_GC_STRESS_PROGRAM=1` (26/26 with `mpz_shadow`).
- **Sanitizers and optimizations off:** a UBSan runtime passes 13/13 AOT and 13/13 JIT; `PYSTACHY_OPT=-all` passes 26/26.
- **Adapted CPython cases (#902):** `mpz_cpython_long_division.py` now crosses the Karatsuba cutoff: 70–83- and 210-digit `test_division` products, and `test_karatsuba` up to 700 digits, balanced and lopsided.
- **New regression:** `mpz_multiplication.py` squares and multiplies solid ones (maximal carries) at 69–281 digits, multiplies quasi-random operands around both cutoffs and at lopsided sizes, and checks:
  - commutativity, distributivity, residues modulo three primes and exact division;
  - squares through the same handle against products of distinct handles;
  - powers up to 40,000 bits.

  CPython checks its digests.
- **Differential C harness** (scratch, not committed), built with GCC `-fsanitize=address,undefined`:
  - About 143,000 checks of the new core against main's, at sizes 0–2,000 limbs: lopsided pairs, squares, all-ones and sparse digit patterns, every operation.
  - 4,500 random large products, squares, sums and quotients compared with CPython's `int`.
  - All identical, with no sanitizer reports.
- **Checks:** `make lint`, `make check-runtime`, `make check-recordings` (1,724 recordings, 0 failed), `make check-repository` and `git diff --check` pass.

CI on `4e301f9`: all 37 checks passed, including the aggregate `make verify`; the fork-only DCO check was skipped.

## Risks and provenance

- **License:** adapted from CPython 3.13.16's `Objects/longobject.c` (PSF License v2), as `THIRD_PARTY_NOTICES` (both copies) and `mpz/README.md` record, with the source hash from #903.
- **Allocation:** Karatsuba allocates more temporaries per product than schoolbook. With a collection at every allocation, `mpz_multiplication.py` takes 0.17 s.
- **Remaining gaps:** squares at 640 digits are 10% slower than CPython's. Multiplication stops at Karatsuba, as CPython's does; there is no Toom-Cook or FFT.
- **AI assistance:** Claude Code wrote the change, the harness and the tests, ran the validation and drafted this description at the maintainer's request. No independent review is implied.

## Checklist

- [x] I reviewed and can explain the complete change.
- [x] I added regression coverage, or explained why it is not applicable.
- [x] The diff contains no raw research, transient handoffs or unapplied prototype patches; reusable checks and fixtures are in maintained locations.
- [x] I have the right to contribute this work and preserved applicable license notices.
- [x] For a PR from a fork: not applicable (branch of this repository).
