-- SPDX-License-Identifier: MIT
import Std

/-! A checked instance is the whole body of a direct Wasm function with tuple
slots and an immediate return. The checker recognizes the concrete ABI indices
of the fixture. The runtime supplies the floor as a wasm32 address stored in
the third i64 word of pys_recursion_state. Instruction semantics, the import
bindings, and the binary-section extractor are trusted. -/
namespace PystachyWasmFrame

private def signedLeb (n : Nat) : List Nat :=
  if n < 64 then [n]
  else (128 + n % 128) :: signedLeb (n / 128)
termination_by n
decreasing_by exact Nat.div_lt_self (by omega) (by decide)

def aligned (bytes : Nat) : Nat := (bytes + 15) / 16 * 16

private def bodyFor (size : Nat) : List Nat :=
  let k := signedLeb size
  [1, 1, 0x7f,                         -- one i32 local for the frame pointer
   0x23, 2, 0xad,                      -- extend the old i32 stack pointer unsigned
   0x23, 1, 0x29, 3, 16, 0x42] ++ k ++ -- i64.load the floor, i64.const size
  [0x7c, 0x54, 0x04, 0x40,             -- if old < floor + size (unsigned)
   0x10, 0, 0x00, 0x0b,                -- call the stack error; unreachable; end
   0x23, 2, 0x41] ++ k ++              -- read the old pointer and i32.const size
  [0x6b, 0x22, 0, 0x24, 2,             -- i32.sub; tee local 0; set the pointer
   0x20, 0, 0x41] ++ k ++              -- get local 0 and i32.const size
  [0x6a, 0x24, 2, 0x0f, 0x00, 0x0b]    -- i32.add; restore; return; unreachable; end

def matchesBody (bytes : Nat) (body : List Nat) : Bool :=
  -- A positive signed i32.const must fit, including its signed LEB encoding.
  0 < bytes && aligned bytes < 2^31 && body == bodyFor (aligned bytes)

/-- For the recognized instruction sequence, execute the success edge of the
widened comparison and the two i32 arithmetic operations. The floor is read
as an i64, so its wasm32 range is a runtime precondition of the theorem. -/
def run (bytes : Nat) (body : List Nat) (sp : BitVec 32) (floor : BitVec 64) :
    Option (BitVec 32 × BitVec 32) :=
  let size := BitVec.ofNat 32 (aligned bytes)
  if matchesBody bytes body && floor + size.setWidth 64 ≤ sp.setWidth 64 then
    let frame := sp - size
    some (frame, frame + size)
  else none

theorem accepted_frame {bytes : Nat} {body : List Nat} {sp frame restored : BitVec 32}
    {floor : BitVec 64} (address : floor.toNat < 2^32)
    (success : run bytes body sp floor = some (frame, restored)) :
    floor.toNat ≤ frame.toNat ∧ frame.toNat + aligned bytes = sp.toNat ∧
    bytes ≤ aligned bytes ∧ aligned bytes % 16 = 0 ∧ restored = sp := by
  simp only [run] at success
  split at success
  next h =>
    simp only [matchesBody, Bool.and_eq_true, decide_eq_true_eq] at h
    have sizeFits := h.1.1.2
    have noWrap : floor.toNat + (BitVec.ofNat 32 (aligned bytes)).toNat < 2^64 := by
      have := (BitVec.ofNat 32 (aligned bytes)).isLt
      omega
    have widened := h.2
    rw [BitVec.le_def, BitVec.toNat_add_of_lt (by
      rwa [BitVec.toNat_setWidth_of_le (by decide : 32 ≤ 64)])] at widened
    simp only [BitVec.toNat_setWidth_of_le (by decide : 32 ≤ 64), BitVec.toNat_ofNat] at widened
    have fits : aligned bytes % 2^32 = aligned bytes := Nat.mod_eq_of_lt (by omega)
    rw [fits] at widened
    cases success
    rw [BitVec.toNat_sub_of_le (by simpa [BitVec.le_def, fits] using
      (show aligned bytes ≤ sp.toNat by omega))]
    simp only [BitVec.toNat_ofNat, fits, BitVec.sub_add_cancel, and_true]
    exact ⟨by omega, by omega, by unfold aligned; omega, by simp [aligned]⟩
  next => simp_all

end PystachyWasmFrame
