# Promoting ints' fit claims

A module that opts in to [promoting ints](../../docs/python-int.md) holds each int as a 64-bit
word and a digit pointer, null exactly where the value fits in signed 64 bits. The compiler
relies on claims that a result fits: an operator needs no promotion, an inline path's 64-bit
result is the exact one, or a large operation's result may take a null digit pointer. A wrong
claim silently turns a large value into its low word. [`PystachyInt.lean`](PystachyInt.lean)
proves them over Lean's unbounded `Int`, and `make check-lean-int` checks each claim the
compiler makes in the test programs that opt in.

## What is proved

Python's `%` and `//` are floor modulo and division (`Int.fmod`, `Int.fdiv`), `>>` is an
arithmetic shift (`>>>`), and `&`, `|` and `^` are two's complement operations on unbounded
ints (`pand`, `por` and `pxor`). The tests compare these with CPython on boundary values.

| Theorem | Claim | Compiler |
|---|---|---|
| `mod_fits` | `x % y` fits where `y` fits and is not zero, whatever `x` is | `PROMOTES`, the inline `%`, `gen_big_known` |
| `shr_fits` | `x >> s` fits where `x` fits, whatever the count | `PROMOTES`, the inline `>>`, `gen_big_known` |
| `bitwise_fits` | `& \| ^` of two values that fit fit | `PROMOTES` |
| `and_fits`, `and_mask` | `x & v` fits where `v` fits and is not negative, whatever `x` is, and masking the result with `v` changes nothing | `gen_big_known`, `gen_big_arith`'s mask |
| `floordiv_fits` | `x // y` of values that fit fits unless `y` is -1 (or zero, which raises) | the inline `//` |
| `shl_exact` | a 64-bit `x << s` with `s < 64` whose arithmetic shift back gives `x` is exactly `x * 2**s` | the inline `<<` |
| `known_fits` | a condition `implies` accepts makes `pys_big_op`'s result fit | `gen_big_known` |

`gen_big_known`'s condition is a formula over four atoms: whether each operand fits and
whether each one's 64-bit word is not negative. `implies` decides, by every assignment of the
atoms, that the formula implies the operator's rule. A word's sign is the value's only where
the value fits, so `known_fits` assumes nothing about it otherwise: a condition that tests a
word's sign alone is rejected. The build checks by kernel reduction that `implies` accepts
the compiler's three conditions and a narrower one and rejects six that must fail.
`Audit.lean` checks the theorems' axioms.

## How IR reaches the checker

[`check_lean_int.py`](../check_lean_int.py) reads a typed-after snapshot and finds each
`select` of a null digit pointer for the result of `rt big.op`, `pys_big_op`. Its fifth operand
is the operator's `BIGOPS` code; a null pointer for an operator without a rule is unsupported.
The other operands must be one promoting int's word (`big.lo`) and digits (`big.hi`), or a
constant. The condition must consist of `and` and `or` of the atoms, each a null test of an
operand's digits (`ptrtoint` of `big.hi` equal to 0) or a sign test of its word (`big.lo` at
least 0), or of literal booleans; anything else is unsupported, not guessed. The Lean
executable `pystachy-int` checks every claim of a snapshot in one run.

```sh
make check-lean-boundary   # build, audit, and the adapter's tests
make check-lean-int        # every claim of the programs that opt in
python3 tools/check_lean_int.py --snapshot inspection/typed-after.json
```

On 2026-11-11 the hosted compiler compiled the 132 test programs that opt in; 29 make 187
claims, in 36 functions, and Lean proved them all, in 12.5 s with four workers.

## Actual inline overflow tests

[`check_lean_inline.py`](../check_lean_inline.py), run by the same arithmetic gate,
inventories `ovf` result words feeding promoting-integer reconstructions and
checks every use of those words against the actual matching overflow flag. A
separately checked control-flow certificate requires the false-overflow edge
before each use, including phi inputs. Repeated loop definitions reset their flag;
call/exception edges remain possible. Unknown conditions retain both successors,
so they cannot establish a fit fact.

A second inventory rejects null-digit reconstructions from unchecked `add`, `sub`
or `mul` of promoting low words, including through scalar casts, masks, selects
and phis. This catches replacing the entire checked operation, in addition to
weakening or swapping its branch.

[`PystachyInline.lean`](PystachyInline.lean) proves that such accepted uses compute
exact unbounded addition, subtraction or multiplication of the signed input
words, with a result that fits. The storage checker separately establishes that
input words are their full promoting values. The actual LLVM signed overflow
intrinsics must implement the modeled `BitVec` operations.

Observed checked operations outside promoting reconstructions are counted
separately; ordinary induction counters and modular arithmetic need different
proofs. This inventory does not prove arbitrary transformed arithmetic provenance.

## Not proved

- The representation: a digit pointer is null exactly where the value fits, and the word is
  then the value. Every result demotes (`docs/python-int.md`), but no proof shows it.
- That the runtime's `pys_big_op`, `pys_mod`, `pys_shr` and `pys_floordiv`, and LLVM's checked
  arithmetic and bitwise operations, compute these operators; the tests compare the results with
  CPython's.
- Only checked `+`, `-`, `*` overflow tests are read from inline IR; the floor-division and
  shift theorems state what those paths must establish without checking their actual guards.
