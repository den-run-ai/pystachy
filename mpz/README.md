# Minimal arbitrary-precision integer core

`mpz.c` is included by `runtime.c`. It adapts MicroPython v1.26.1's
`mpn_mul_dig_add_dig`, `mpn_mul` and `mpn_div` arithmetic to immutable,
garbage-collected values with an inline array of 30-bit digits in `uint32_t`
slots. The sign and length occupy one signed 64-bit word. Published operands
are never modified; temporary results and conversion scratch are private.

Upstream: <https://github.com/micropython/micropython/blob/v1.26.1/py/mpz.c>

SHA-256 of the inspected original `py/mpz.c`:
`6be02893c2c7f2f38cd4bb41f2398d2c72187c9064b1d5910a6a933aec1d40ea`.
The source's MIT license is preserved in `mpz.c` and the repository notices.

Text conversion follows CPython 3.13.16's `Objects/longobject.c`:
`long_from_binary_base` packs power-of-two bases in linear time,
`long_from_non_binary_base` multiplies and adds the largest group of digits
below 2^30 (nine decimal digits) per pass, and
`long_to_decimal_string_internal` converts to base 10^9 in one pass per input
digit, with CPython's bound on the result's length. These parts are used under
the Python Software Foundation License Version 2 (see the repository notices).
The parser also checks CPython's errors in its order: syntax, then the digit
limit, then a base-0 literal's leading zero.

Upstream: <https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Objects/longobject.c>

SHA-256 of the inspected `Objects/longobject.c`, from python.org's
`Python-3.13.16.tar.xz`:
`8f3c1c8e496b5eab4ebca0b908bea0fe82a5815882cbc6e4edcb16b437eea0e5`.

The Pystachy adapter supplies allocation and size checks, parsing, sign and
floor-division rules, infinite two's-complement bitwise operations, shifts,
64-bit checked conversion, hashing and decimal formatting. Division and
normalization use indexed loops so they do not form pointers before arrays.
No external bigint library or embedded CPython is needed.

Schoolbook multiplication and normalized long division prioritize a compact
implementation; this is not a claim of GMP or CPython performance. The parser
reuses Pystachy's Unicode numeric normalization and CPython-style base/prefix/
underscore rules. Non-power-of-two input and decimal output use CPython's
default 4300-digit limit; changing that limit is not supported by this module.
