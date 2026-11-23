-- SPDX-License-Identifier: MIT
import Std

/-! The numeric class ID indexes a row of four wasm32 function pointers. The
fixture checker inspects a complete emitted start body, element segment and
initial data segment. It assumes the Wasm semantics, function and import
bindings, and the section extractor. The reactor's C layout is a separate ABI
obligation. This does not model callback bodies, traps or host execution. -/
namespace PystachyWasmDispatch

def slot (base id : Nat) (field : Fin 4) : Nat := base + 16 * id + 4 * field.val

/-- A complete in-memory table gives every four-byte load its exact wasm32
address, including the last byte of a table ending at the linear memory limit. -/
theorem slot_in_bounds {base rows id : Nat} (field : Fin 4)
    (valid : id < rows) (fits : base + 16 * rows ≤ 2^32) :
    (BitVec.ofNat 32 (slot base id field)).toNat = slot base id field ∧
    base ≤ slot base id field ∧ slot base id field + 4 ≤ base + 16 * rows := by
  have := field.isLt
  simp only [slot, BitVec.toNat_ofNat]
  rw [Nat.mod_eq_of_lt (by omega)]
  omega

/-- Distinct class and operation pairs cannot overlap, even by a single byte. -/
theorem slots_disjoint (base a b : Nat) (fa fb : Fin 4)
    (different : a ≠ b ∨ fa ≠ fb) :
    slot base a fa + 4 ≤ slot base b fb ∨ slot base b fb + 4 ≤ slot base a fa := by
  have := fa.isLt
  have := fb.isLt
  simp only [slot]
  by_cases h : fa.val = fb.val
  · have : fa = fb := Fin.ext h
    omega
  · omega

-- All LEB immediates in this two-class module fit in one byte.
private def store (id : Nat) (field : Fin 4) (index : Nat) : List Nat :=
  [0x23, 0, 0x20, 0, 0x41, index, 0x6a, 0x36, 2, slot 8 id field]

def matchesFixture (start elems body data : List Nat) : Bool :=
  start == [7] &&
  -- Passive funcref segment: A.repr, A.eq, A.cmp, B.repr, B.hash.
  elems == [1, 1, 0, 5, 6, 5, 4, 3, 2] &&
  -- The reactor's existing table may be any nonzero size. The initializer
  -- traps on failed growth and copies the new entries after its old size.
  body == ([1, 1, 0x7f, 0xd0, 0x70, 0x41, 5, 0xfc, 15, 0, 0x21, 0,
            0x20, 0, 0x41, 0x7f, 0x46, 0x04, 0x40, 0, 0x0b,
            0x20, 0, 0x41, 0, 0x41, 5, 0xfc, 12, 0, 0] ++
           store 0 0 0 ++ store 0 1 1 ++ store 0 2 2 ++ store 1 0 3 ++ store 1 3 4 ++
           -- Register data + 8 and two rows with imported setter 0, after all stores.
           [0x23, 0, 0x41, 8, 0x6a, 0x41, 2, 0x10, 0, 0x0b]) &&
  -- One active data segment at env.data. Uninstalled fields are null.
  data == ([1, 0, 0x23, 0, 0x0b, 40] ++ List.replicate 40 0)

end PystachyWasmDispatch
