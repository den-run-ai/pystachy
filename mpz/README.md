# Minimal arbitrary-precision integer core

`mpz.c` is included by `runtime.c`. It adapts MicroPython v1.26.1's
`mpn_mul_dig_add_dig` to immutable, garbage-collected values with an inline
array of 30-bit digits in `uint32_t` slots. The sign and length occupy one signed
64-bit word. Published operands are never modified; temporary results and
conversion scratch are private.

Upstream: <https://github.com/micropython/micropython/blob/v1.26.1/py/mpz.c>

SHA-256 of the inspected original `py/mpz.c`:
`6be02893c2c7f2f38cd4bb41f2398d2c72187c9064b1d5910a6a933aec1d40ea`.
The source's MIT license is preserved in `mpz.c` and the repository notices.

Text conversion and arithmetic follow CPython 3.13.16's
`Objects/longobject.c`:

- `long_from_binary_base` packs power-of-two bases in linear time,
  `long_from_non_binary_base` multiplies and adds the largest group of digits
  below 2^30 (nine decimal digits) per pass, and
  `long_to_decimal_string_internal` converts to base 10^9 in one pass per input
  digit, with CPython's bound on the result's length.
- `x_add` and `x_sub` run separate loops over the shorter operand's digits and
  the carry or borrow through the longer one's.
- `x_mul` multiplies schoolbook, squaring with half the digit products when
  both operands are the same value; `k_mul` (with `kmul_split`, `v_iadd` and
  `v_isub`) uses Karatsuba's three half-size products above CPython's cutoff of
  70 digits (140 for squares), and `k_lopsided_mul` multiplies a much longer
  operand slice by slice.
- `x_divrem` divides by Knuth's Algorithm D: both operands are shifted so the
  divisor's top digit has its high bit set, and each quotient digit is
  estimated from two dividend digits, corrected with the divisor's second digit
  and fixed by at most one add-back. `divrem1` divides by a one-digit divisor.

These parts are used under the Python Software Foundation License Version 2
(see the repository notices).
The parser also checks CPython's errors in its order: syntax, then the digit
limit, then a base-0 literal's leading zero.

Upstream: <https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Objects/longobject.c>

SHA-256 of the inspected `Objects/longobject.c`, from python.org's
`Python-3.13.16.tar.xz`:
`8f3c1c8e496b5eab4ebca0b908bea0fe82a5815882cbc6e4edcb16b437eea0e5`.

The Pystachy adapter supplies allocation and size checks, parsing, sign and
floor-division rules, infinite two's-complement bitwise operations, shifts,
64-bit checked conversion and hashing. Its loops are indexed so they never form
a pointer before an array.
No external bigint library or embedded CPython is needed.

Long division is quadratic and multiplication stops at Karatsuba, as in
CPython for these sizes; this is not a claim of GMP performance. The parser
reuses Pystachy's Unicode numeric normalization and CPython-style base/prefix/
underscore rules. Non-power-of-two input and decimal output use CPython's
default 4300-digit limit; changing that limit is not supported by this module.
