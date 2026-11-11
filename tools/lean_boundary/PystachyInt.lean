-- SPDX-License-Identifier: MIT
/-!
# Promoting ints that fit in 64 bits

In a module that opts in to promoting ints (`# pystachy: python-int`, docs/python-int.md) an int
is a 64-bit word and a digit pointer, null exactly where the value fits in 64 bits
(src/pystachy_compiler/bigints.py). The compiler relies on fit claims about Python's int
operators; a wrong one turns a large result into its low word. This module proves them, over
Lean's `Int`:

* `PROMOTES`: `% & | ^ >>` of two values that fit fit, so they need no promotion
  (`mod_fits`, `bitwise_fits`, `shr_fits`); `//` does except for `-2**63 // -1`
  (`floordiv_fits`).
* `gen_big_arith`'s inline paths where both operands fit: `<<` by a count below 64 whose shift
  back gives the operand is exact (`shl_exact`); `//` by other than -1 fits.
* `gen_big_known`: after the general `pys_big_op`, the result's digit pointer is set to null
  under a condition on the operands' words. `implies` decides that a condition implies a proved
  rule's precondition, and `known_fits` shows that a condition `implies` accepts makes the
  result fit for all operands.

Python's `%` and `//` are floor modulo and division (`Int.fmod`, `Int.fdiv`), `>>` an
arithmetic shift (`>>>` on `Int`, floor division by a power of two), and `& | ^` two's
complement operations on unbounded ints (`pand`, `por`, `pxor`).
-/

namespace PystachyInt

/-- A value a promoting int holds in its 64-bit word, with a null digit pointer. -/
def Fits (x : Int) : Prop := -2 ^ 63 ≤ x ∧ x < 2 ^ 63

instance (x : Int) : Decidable (Fits x) := inferInstanceAs (Decidable (_ ∧ _))

/-- `x % y` fits whenever `y` fits (and is not zero, which raises): the remainder takes `y`'s
sign and is smaller than it in magnitude. -/
theorem mod_fits (x y : Int) (hy : Fits y) (h0 : y ≠ 0) : Fits (x.fmod y) := by
  obtain ⟨lo, hi⟩ := hy
  rcases Int.lt_or_gt_of_ne h0 with neg | pos
  · -- y < 0: y < x.fmod y ≤ 0, from the positive case for -x and -y
    have p : 0 < -y := by omega
    have a := Int.fmod_nonneg_of_pos (-x) p
    have b := Int.fmod_lt_of_pos (-x) p
    have e : x.fmod y = -((-x).fmod (-y)) := by
      rw [← Int.neg_fmod_neg, Int.neg_neg, Int.neg_neg]
    rw [e]
    constructor <;> omega
  · have a := Int.fmod_nonneg_of_pos x pos
    have b := Int.fmod_lt_of_pos x pos
    constructor <;> omega

/-- `x >> s` fits whenever `x` fits: an arithmetic shift moves a value toward 0 or -1 without
passing it, whatever the count. -/
theorem shr_fits (x : Int) (s : Nat) (hx : Fits x) : Fits (x >>> s) := by
  obtain ⟨lo, hi⟩ := hx
  rcases Int.le_total 0 x with nonneg | nonpos
  · have a := Int.le_shiftRight_of_nonneg (s := s) nonneg
    have b := Int.shiftRight_le_of_nonneg (s := s) nonneg
    constructor <;> omega
  · have a := Int.le_shiftRight_of_nonpos (s := s) nonpos
    have b := Int.shiftRight_le_of_nonpos (s := s) nonpos
    constructor <;> omega

/-- Floor division by a positive divisor lies between `min x 0` and `max x 0`. -/
theorem fdiv_pos_bounds (x y : Int) (hy : 0 < y) :
    (0 ≤ x → 0 ≤ x.fdiv y ∧ x.fdiv y ≤ x) ∧ (x < 0 → x ≤ x.fdiv y ∧ x.fdiv y ≤ 0) := by
  rw [Int.fdiv_eq_ediv_of_nonneg x (Int.le_of_lt hy)]
  constructor
  · intro hx
    exact ⟨Int.ediv_nonneg hx (Int.le_of_lt hy), Int.ediv_le_self y hx⟩
  · intro hx
    constructor
    · apply Int.le_ediv_of_mul_le hy
      have : x * y ≤ x * 1 := Int.mul_le_mul_of_nonpos_left (by omega) (by omega)
      omega
    · have := Int.ediv_le_ediv hy (Int.le_of_lt hx)
      simpa using this

/-- `x // y` of two values that fit fits, except `-2**63 // -1`: the inline path sends
`y = -1` to `pys_big_op`, and division by zero raises. -/
theorem floordiv_fits (x y : Int) (hx : Fits x) (hy : Fits y) (h0 : y ≠ 0) (hm : y ≠ -1) :
    Fits (x.fdiv y) := by
  obtain ⟨xlo, xhi⟩ := hx
  obtain ⟨ylo, yhi⟩ := hy
  rcases Int.lt_or_gt_of_ne h0 with neg | pos
  · -- y ≤ -2: x // y = (-x) // (-y), and -x lies in (-2^63, 2^63]
    have e : x.fdiv y = (-x).fdiv (-y) := (Int.neg_fdiv_neg x y).symm
    rw [e]
    have p : 0 < -y := by omega
    obtain ⟨a, b⟩ := fdiv_pos_bounds (-x) (-y) p
    rcases Int.le_total 0 (-x) with nn | np
    · obtain ⟨c, d⟩ := a nn
      -- (-x) // (-y) ≤ (-x) / 2 < 2^63 needs -y ≥ 2: bound by division by 2
      have two : (-x).fdiv (-y) * 2 ≤ -x := by
        have m := Int.fmod_add_mul_fdiv (-x) (-y)
        have r := Int.fmod_nonneg_of_pos (-x) p
        have : 2 * (-x).fdiv (-y) ≤ (-y) * (-x).fdiv (-y) :=
          Int.mul_le_mul_of_nonneg_right (show (2 : Int) ≤ -y by omega) c
        omega
      constructor <;> omega
    · rcases Int.lt_or_eq_of_le np with lt | eq
      · obtain ⟨c, d⟩ := b lt
        constructor <;> omega
      · rw [eq]
        simp [Fits]
  · obtain ⟨a, b⟩ := fdiv_pos_bounds x y pos
    rcases Int.le_total 0 x with nn | np
    · obtain ⟨c, d⟩ := a nn
      constructor <;> omega
    · rcases Int.lt_or_eq_of_le np with lt | eq
      · obtain ⟨c, d⟩ := b lt
        constructor <;> omega
      · subst eq
        simp [Fits]

/-- The inline `<<` (`gen_big_arith`): `r` is the 64-bit shift of `x` by `s < 64`, a value that
fits and differs from `x * 2^s` by a multiple of 2^64. Where the arithmetic shift back gives `x`,
`r` is exactly `x * 2^s`. -/
theorem shl_exact (x r k : Int) (s : Nat) (hs : s < 64) (hr : Fits r)
    (wrap : r = x * 2 ^ s - k * 2 ^ 64) (back : r >>> s = x) : r = x * 2 ^ s := by
  obtain ⟨lo, hi⟩ := hr
  have hq : 0 < 2 ^ s := Nat.two_pow_pos s
  have hq2 : 2 ^ s ≤ 2 ^ 63 := Nat.pow_le_pow_right (by decide) (by omega)
  rw [Int.shiftRight_eq_div_pow] at back
  have cast : ((2 ^ s : Nat) : Int) = (2 : Int) ^ s := by simp
  rw [← cast] at wrap ⊢
  have e := Int.emod_add_mul_ediv r ((2 ^ s : Nat) : Int)
  have h1 := Int.emod_nonneg r (b := ((2 ^ s : Nat) : Int)) (by omega)
  have h2 := Int.emod_lt_of_pos r (b := ((2 ^ s : Nat) : Int)) (by omega)
  rw [back] at e
  rw [Int.mul_comm x] at wrap ⊢
  generalize 2 ^ s = q at *
  generalize (q : Int) * x = m at *
  omega

/-- Python's `x & y`, in infinite two's complement: a negative `-(m+1)` is `~m`, so
`m & ~n` keeps `m`'s bits that `n` lacks, and `~m & ~n` is `~(m | n)`. -/
def pand : Int → Int → Int
  | .ofNat m, .ofNat n => .ofNat (m &&& n)
  | .ofNat m, .negSucc n => .ofNat (m ^^^ (m &&& n))
  | .negSucc m, .ofNat n => .ofNat (n ^^^ (n &&& m))
  | .negSucc m, .negSucc n => .negSucc (m ||| n)

/-- Python's `x | y` and `x ^ y`, in infinite two's complement. -/
def por : Int → Int → Int
  | .ofNat m, .ofNat n => .ofNat (m ||| n)
  | .ofNat m, .negSucc n => .negSucc (n ^^^ (n &&& m))
  | .negSucc m, .ofNat n => .negSucc (m ^^^ (m &&& n))
  | .negSucc m, .negSucc n => .negSucc (m &&& n)

def pxor : Int → Int → Int
  | .ofNat m, .ofNat n => .ofNat (m ^^^ n)
  | .ofNat m, .negSucc n => .negSucc (m ^^^ n)
  | .negSucc m, .ofNat n => .negSucc (m ^^^ n)
  | .negSucc m, .negSucc n => .ofNat (m ^^^ n)

theorem xor_and_le (n m : Nat) : n ^^^ (n &&& m) ≤ n :=
  Nat.le_of_testBit fun i h => by
    simp only [Nat.testBit_xor, Nat.testBit_and] at h
    cases a : n.testBit i <;> simp_all

/-- `x & v` of a nonnegative `v` lies in `[0, v]`, whatever `x` is. -/
theorem and_bounded (x : Int) (n : Nat) :
    0 ≤ pand x (.ofNat n) ∧ pand x (.ofNat n) ≤ .ofNat n ∧
    0 ≤ pand (.ofNat n) x ∧ pand (.ofNat n) x ≤ .ofNat n := by
  cases x with
  | ofNat m => exact ⟨Int.natCast_nonneg _, Int.ofNat_le.mpr Nat.and_le_right,
      Int.natCast_nonneg _, Int.ofNat_le.mpr Nat.and_le_left⟩
  | negSucc m => exact ⟨Int.natCast_nonneg _, Int.ofNat_le.mpr (xor_and_le n m),
      Int.natCast_nonneg _, Int.ofNat_le.mpr (xor_and_le n m)⟩

/-- `x & v` and `v & x` fit where `v` fits and is not negative, whatever `x` is. -/
theorem and_fits (x : Int) (n : Nat) (hv : Fits (.ofNat n)) :
    Fits (pand x (.ofNat n)) ∧ Fits (pand (.ofNat n) x) := by
  obtain ⟨_, hi⟩ := hv
  obtain ⟨a, b, c, d⟩ := and_bounded x n
  exact ⟨⟨by omega, by omega⟩, ⟨by omega, by omega⟩⟩

/-- `gen_big_arith` masks the known `&` result's low word with such an operand: a no-op, as the
result's bits are the operand's. -/
theorem and_mask (x : Int) (n : Nat) : pand (pand x (.ofNat n)) (.ofNat n) = pand x (.ofNat n) := by
  cases x with
  | ofNat m =>
    show Int.ofNat ((m &&& n) &&& n) = Int.ofNat (m &&& n)
    congr 1
    exact Nat.eq_of_testBit_eq fun i => by
      simp only [Nat.testBit_and]; cases m.testBit i <;> cases n.testBit i <;> rfl
  | negSucc m =>
    show Int.ofNat ((n ^^^ (n &&& m)) &&& n) = Int.ofNat (n ^^^ (n &&& m))
    congr 1
    exact Nat.eq_of_testBit_eq fun i => by
      simp only [Nat.testBit_and, Nat.testBit_xor]; cases m.testBit i <;> cases n.testBit i <;> rfl

theorem fits_word (x : Int) (h : Fits x) :
    (∃ m, x = .ofNat m ∧ m < 2 ^ 63) ∨ (∃ m, x = .negSucc m ∧ m < 2 ^ 63) := by
  obtain ⟨lo, hi⟩ := h
  cases x with
  | ofNat m => exact .inl ⟨m, rfl, by simp only [Int.ofNat_eq_natCast] at hi; omega⟩
  | negSucc m => exact .inr ⟨m, rfl, by rw [Int.negSucc_eq] at lo; omega⟩

theorem ofNat_fits {m : Nat} (h : m < 2 ^ 63) : Fits (.ofNat m) := by
  constructor <;> simp only [Int.ofNat_eq_natCast] <;> omega

theorem negSucc_fits {m : Nat} (h : m < 2 ^ 63) : Fits (.negSucc m) := by
  constructor <;> rw [Int.negSucc_eq] <;> omega

/-- `& | ^` of two values that fit fit. -/
theorem bitwise_fits (x y : Int) (hx : Fits x) (hy : Fits y) :
    Fits (pand x y) ∧ Fits (por x y) ∧ Fits (pxor x y) := by
  rcases fits_word x hx with ⟨m, rfl, hm⟩ | ⟨m, rfl, hm⟩ <;>
  rcases fits_word y hy with ⟨n, rfl, hn⟩ | ⟨n, rfl, hn⟩
  · exact ⟨ofNat_fits (Nat.and_lt_two_pow _ hn), ofNat_fits (Nat.or_lt_two_pow hm hn),
      ofNat_fits (Nat.xor_lt_two_pow hm hn)⟩
  · exact ⟨ofNat_fits (Nat.lt_of_le_of_lt (xor_and_le m n) hm),
      negSucc_fits (Nat.lt_of_le_of_lt (xor_and_le n m) hn), negSucc_fits (Nat.xor_lt_two_pow hm hn)⟩
  · exact ⟨ofNat_fits (Nat.lt_of_le_of_lt (xor_and_le n m) hn),
      negSucc_fits (Nat.lt_of_le_of_lt (xor_and_le m n) hm), negSucc_fits (Nat.xor_lt_two_pow hm hn)⟩
  · exact ⟨negSucc_fits (Nat.or_lt_two_pow hm hn), negSucc_fits (Nat.and_lt_two_pow _ hn),
      ofNat_fits (Nat.xor_lt_two_pow hm hn)⟩

/-! ## `gen_big_known`'s conditions

The condition is a formula over four atoms of the operands `x` and `y`: whether each fits (its
digit pointer is null) and whether its 64-bit word is not negative. The word is the value only
where the value fits, so a word's sign says nothing about a value that does not. -/

inductive Atom where
  | fitsX | fitsY | nonnegX | nonnegY
  deriving DecidableEq, Repr

inductive Cond where
  | atom (a : Atom)
  | and (a b : Cond)
  | or (a b : Cond)
  | true
  | false
  deriving Repr

def Cond.eval (env : Atom → Bool) : Cond → Bool
  | .atom a => env a
  | .and a b => a.eval env && b.eval env
  | .or a b => a.eval env || b.eval env
  | .true => Bool.true
  | .false => Bool.false

/-- The operators with a fit rule (`BIGOPS` codes 4, 9 and 5). -/
inductive Op where
  | mod | shr | land
  deriving DecidableEq, Repr

/-- Each rule's precondition: `x % y` fits where `y` fits; `x >> y` where `x` fits; `x & y`
where an operand fits and is not negative. -/
def pre : Op → Cond
  | .mod => .atom .fitsY
  | .shr => .atom .fitsX
  | .land => .or (.and (.atom .fitsX) (.atom .nonnegX)) (.and (.atom .fitsY) (.atom .nonnegY))

def envs : List (Atom → Bool) :=
  [false, true].flatMap fun a => [false, true].flatMap fun b => [false, true].flatMap fun c =>
    [false, true].map fun d => fun
      | .fitsX => a | .fitsY => b | .nonnegX => c | .nonnegY => d

/-- The condition implies the rule's precondition under every assignment of the atoms. -/
def implies (c : Cond) (op : Op) : Bool :=
  envs.all fun env => !c.eval env || (pre op).eval env

theorem env_listed (env : Atom → Bool) : ∃ e ∈ envs, ∀ a, e a = env a := by
  refine ⟨fun | .fitsX => env .fitsX | .fitsY => env .fitsY | .nonnegX => env .nonnegX
               | .nonnegY => env .nonnegY, ?_, fun a => by cases a <;> rfl⟩
  simp only [envs, List.mem_flatMap, List.mem_map, List.mem_cons]
  refine ⟨env .fitsX, by cases env .fitsX <;> simp, env .fitsY, by cases env .fitsY <;> simp,
    env .nonnegX, by cases env .nonnegX <;> simp, env .nonnegY, by cases env .nonnegY <;> simp, ?_⟩
  funext a
  cases a <;> rfl

theorem eval_congr (c : Cond) {e env : Atom → Bool} (h : ∀ a, e a = env a) :
    c.eval e = c.eval env := by
  induction c with
  | atom a => exact h a
  | and a b iha ihb => simp [Cond.eval, iha, ihb]
  | or a b iha ihb => simp [Cond.eval, iha, ihb]
  | true => rfl
  | false => rfl

/-- An accepted condition implies the rule's precondition for any assignment of the atoms. -/
theorem implies_sound {c : Cond} {op : Op} (ok : implies c op = true) (env : Atom → Bool)
    (holds : c.eval env = true) : (pre op).eval env = true := by
  obtain ⟨e, member, same⟩ := env_listed env
  have := List.all_eq_true.mp ok e member
  rw [eval_congr c same, eval_congr (pre op) same, holds] at this
  simpa using this

/-- The atoms of operands `x` and `y`: each fits exactly where its digit pointer is null, and a
word's sign is the value's where the value fits; elsewhere it is arbitrary. -/
structure Atoms (env : Atom → Bool) (x y : Int) : Prop where
  fitsX : env .fitsX = decide (Fits x)
  fitsY : env .fitsY = decide (Fits y)
  nonnegX : Fits x → env .nonnegX = decide (0 ≤ x)
  nonnegY : Fits y → env .nonnegY = decide (0 ≤ y)

/-- `pys_big_op`'s result, where it returns one: `%` raises for a zero divisor and `>>` for a
negative count. -/
def result : Op → Int → Int → Int
  | .mod, x, y => x.fmod y
  | .shr, x, y => x >>> y.toNat
  | .land, x, y => pand x y

def returns : Op → Int → Int → Prop
  | .mod, _, y => y ≠ 0
  | .shr, _, y => 0 ≤ y
  | .land, _, _ => True

theorem nonneg_word {x : Int} (h : 0 ≤ x) : ∃ n : Nat, x = .ofNat n :=
  ⟨x.toNat, by simp [Int.toNat_of_nonneg h]⟩

/-- The guarantee: wherever a condition `implies` accepts holds of the operands' atoms, the
result fits, so a null digit pointer represents it. -/
theorem known_fits {c : Cond} {op : Op} (ok : implies c op = true) {env : Atom → Bool}
    {x y : Int} (atoms : Atoms env x y) (holds : c.eval env = true) (ret : returns op x y) :
    Fits (result op x y) := by
  have p := implies_sound ok env holds
  cases op with
  | mod =>
    simp only [pre, Cond.eval, atoms.fitsY, decide_eq_true_eq] at p
    exact mod_fits x y p ret
  | shr =>
    simp only [pre, Cond.eval, atoms.fitsX, decide_eq_true_eq] at p
    exact shr_fits x y.toNat p
  | land =>
    simp only [pre, Cond.eval, Bool.or_eq_true, Bool.and_eq_true] at p
    rcases p with ⟨fx, nx⟩ | ⟨fy, ny⟩
    · have hx : Fits x := by simpa [atoms.fitsX] using fx
      have h0 : 0 ≤ x := by simpa [atoms.nonnegX hx] using nx
      obtain ⟨n, rfl⟩ := nonneg_word h0
      exact (and_fits y n hx).2
    · have hy : Fits y := by simpa [atoms.fitsY] using fy
      have h0 : 0 ≤ y := by simpa [atoms.nonnegY hy] using ny
      obtain ⟨n, rfl⟩ := nonneg_word h0
      exact (and_fits x n hy).1

/-! The compiler's own conditions, and conditions it must not use. -/

example : implies (.atom .fitsY) .mod = true := by decide
example : implies (.atom .fitsX) .shr = true := by decide
example : implies (.or (.and (.atom .fitsX) (.atom .nonnegX))
    (.and (.atom .fitsY) (.atom .nonnegY))) .land = true := by decide
-- a narrower condition is also sound
example : implies (.and (.atom .fitsY) (.atom .fitsX)) .mod = true := by decide
-- the dividend fitting says nothing of `x % y` with a large `y`
example : implies (.atom .fitsX) .mod = false := by decide
-- nor does the count's fitting of `x >> y` with a large `x`
example : implies (.atom .fitsY) .shr = false := by decide
-- an operand that fits but may be negative does not bound `x & y`
example : implies (.or (.atom .fitsX) (.atom .fitsY)) .land = false := by decide
-- a word's sign without the operand fitting is the low word of a large value
example : implies (.or (.atom .nonnegX) (.atom .nonnegY)) .land = false := by decide
-- one operand's fitting and the other's sign
example : implies (.and (.atom .fitsX) (.atom .nonnegY)) .land = false := by decide
example : implies .true .mod = false := by decide

end PystachyInt
