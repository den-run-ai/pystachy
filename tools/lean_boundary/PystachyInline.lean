-- SPDX-License-Identifier: MIT
import PystachyBoundary
import PystachyInt

/-!
# Actual checked arithmetic overflow edges

The adapter inventories `ovf` result words feeding promoting reconstructions
and normalizes the actual branch on each matching overflow flag. The executable boundary checker
proves that every reachable use has the `exact` (false overflow) tag.

These corollaries connect that checked graph fact to signed 64-bit arithmetic.
They trust the correspondence from `ovf` to LLVM's signed overflow intrinsics;
they do not assume that the unchecked machine result equals the integer result.
Input low words represent full Python integers only when their separate storage
fit obligations hold. Runtime arithmetic and LLVM lowering remain outside this
model.
-/
namespace PystachyInline
open PystachyBoundary PystachyInt

inductive Op where
  | add | sub | mul
  deriving DecidableEq, Repr

def result : Op → Int → Int → Int
  | .add, x, y => x + y
  | .sub, x, y => x - y
  | .mul, x, y => x * y

def word : Op → BitVec 64 → BitVec 64 → BitVec 64
  | .add, x, y => x + y
  | .sub, x, y => x - y
  | .mul, x, y => x * y

def overflow : Op → BitVec 64 → BitVec 64 → Bool
  | .add, x, y => x.saddOverflow y
  | .sub, x, y => x.ssubOverflow y
  | .mul, x, y => x.smulOverflow y

def overflowTag (flag : Bool) : Tag := if flag then "overflow" else "exact"

theorem no_overflow_exact (op : Op) (x y : BitVec 64)
    (safe : overflow op x y = false) :
    (word op x y).toInt = result op x.toInt y.toInt := by
  cases op with
  | add => exact BitVec.toInt_add_of_not_saddOverflow (by simpa [overflow] using safe)
  | sub => exact BitVec.toInt_sub_of_not_ssubOverflow (by simpa [overflow] using safe)
  | mul => exact BitVec.toInt_mul_of_not_smulOverflow (by simpa [overflow] using safe)

theorem no_overflow_fits (op : Op) (x y : BitVec 64)
    (safe : overflow op x y = false) : Fits (result op x.toInt y.toInt) := by
  rw [← no_overflow_exact op x y safe]
  exact ⟨BitVec.le_toInt _, BitVec.toInt_lt⟩

/-- A graph-checked use computes the unbounded result exactly, rather than a
wrapped machine word, when its predicate denotes the matching overflow flag. -/
theorem accepted_arithmetic_exact {program : Program} {certificate : Certificate}
    {initial : Tags} {state : State} {location : Location} {next : Nat}
    {op : Op} {x y : BitVec 64}
    (checked : check program certificate = true)
    (reachable : Reachable program initial state)
    (read : program.nodes[state.pc]? = some (.payload location ["exact"] next))
    (interpreted : state.tags location = overflowTag (overflow op x y)) :
    (word op x y).toInt = result op x.toInt y.toInt ∧ Fits (result op x.toInt y.toInt) := by
  have accepted := accepted_payload_safe checked reachable read
  have flag : overflow op x y = false := by
    cases h : overflow op x y with
    | false => rfl
    | true => simp [interpreted, overflowTag, h] at accepted
  exact ⟨no_overflow_exact op x y flag, no_overflow_fits op x y flag⟩

-- Boundary examples check the same Bool direction used by emitted cbrs.
example : overflow .add 9223372036854775807#64 1#64 = true := by decide
example : overflow .sub (-9223372036854775808 : BitVec 64) 1#64 = true := by decide
example : overflow .mul (-9223372036854775808 : BitVec 64) (-1 : BitVec 64) = true := by decide
example : overflow .mul (-9223372036854775808 : BitVec 64) 1#64 = false := by decide

end PystachyInline
