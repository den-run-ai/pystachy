-- SPDX-License-Identifier: MIT
import PystachyAlias

/-! A bounded, initialized numeric-list companion. The C adapter supplies the
scanned header transfer, scanned array allocation and actual setter/getter word
offsets. Arbitrary other cells are retained in the model. The concrete collector,
materialization, resizing and the C-to-model adapter are not verified here. -/
namespace PystachyCompanion
open PystachyAlias

structure Contract where
  header : Transfer
  arrayScanned : Bool
  prefixWords : Nat
  storeOffset : Nat
  readOffset : Nat
  deriving Repr, DecidableEq

def Accepted (contract : Contract) : Prop :=
  PystachyAlias.Accepted contract.header ∧ contract.arrayScanned = true ∧
  0 < contract.prefixWords ∧ contract.storeOffset = contract.prefixWords ∧
  contract.readOffset = contract.storeOffset

instance (contract : Contract) : Decidable (Accepted contract) := by
  unfold Accepted
  infer_instance

def check (contract : Contract) : Bool := decide (Accepted contract)

def store (memory : Nat → Nat) (word value : Nat) : Nat → Nat :=
  fun address => if address = word then value else memory address

/-- A store and subsequent load preserve the original box address, for arbitrary
other cells. The initialized, stable companion is a precondition. -/
theorem accepted_identity_roundtrip {contract : Contract}
    (accepted : check contract = true) (memory : Nat → Nat) (index box : Nat) :
    store memory (index + contract.storeOffset) box (index + contract.readOffset) = box := by
  have valid : Accepted contract := of_decide_eq_true accepted
  simp [store, valid.2.2.2.2]

def tracesArray (scanned : Bool) (words : Nat) (memory : Nat → Nat) (target : Nat) : Prop :=
  target ≠ 0 ∧ scanned = true ∧ ∃ word, word < words ∧ memory word = target

/-- The exact stored identity lies within the scanned extent for every live
index, not just the concrete sizes used by regression tests. -/
theorem accepted_traces_identity {contract : Contract}
    (accepted : check contract = true) (memory : Nat → Nat) (capacity index box : Nat)
    (within : index < capacity) (nonnull : box ≠ 0) :
    tracesArray contract.arrayScanned (capacity + contract.prefixWords)
      (store memory (index + contract.storeOffset) box) box := by
  have valid : Accepted contract := of_decide_eq_true accepted
  refine ⟨nonnull, valid.2.1, index + contract.storeOffset, ?_, ?_⟩
  · rw [valid.2.2.2.1]
    omega
  · simp [store]

/-- List header and companion array provide both downstream edges. Only the
meaning of scanned storage in the concrete heap remains an external premise. -/
theorem accepted_root_chain {contract : Contract}
    (accepted : check contract = true) (memory : Nat → Nat)
    (capacity index list companion box : Nat) (edges : Nat → Nat → Prop)
    (within : index < capacity) (companionNonzero : companion ≠ 0) (boxNonzero : box ≠ 0)
    (headerEdge : ∀ target, traces contract.header 0 companion target → edges list target)
    (arrayEdge : ∀ target, tracesArray contract.arrayScanned (capacity + contract.prefixWords)
      (store memory (index + contract.storeOffset) box) target → edges companion target) :
    Reachable edges list box := by
  have valid : Accepted contract := of_decide_eq_true accepted
  have headerChecked : PystachyAlias.check contract.header = true :=
    decide_eq_true valid.1
  exact .step (.step .root
    (headerEdge companion (accepted_traces_reference headerChecked 0 companion companionNonzero)))
    (arrayEdge box (accepted_traces_identity accepted memory capacity index box within boxNonzero))

/-- Compose the already verified Any box transfer with the newly established
list/companion edges. No unproved downstream child-edge hypothesis is needed. -/
theorem accepted_boxed_root_chain {outer : Transfer} {contract : Contract}
    (outerAccepted : PystachyAlias.check outer = true) (accepted : check contract = true)
    (memory : Nat → Nat) (capacity index outerBox list companion box : Nat)
    (edges : Nat → Nat → Prop) (within : index < capacity)
    (listNonzero : list ≠ 0) (companionNonzero : companion ≠ 0) (boxNonzero : box ≠ 0)
    (outerEdge : ∀ target, traces outer 0 list target → edges outerBox target)
    (headerEdge : ∀ target, traces contract.header 0 companion target → edges list target)
    (arrayEdge : ∀ target, tracesArray contract.arrayScanned (capacity + contract.prefixWords)
      (store memory (index + contract.storeOffset) box) target → edges companion target) :
    Reachable edges outerBox box := by
  have valid : Accepted contract := of_decide_eq_true accepted
  have headerChecked : PystachyAlias.check contract.header = true := decide_eq_true valid.1
  exact .step (.step (.step .root
    (outerEdge list (accepted_traces_reference outerAccepted 0 list listNonzero)))
    (headerEdge companion (accepted_traces_reference headerChecked 0 companion companionNonzero)))
    (arrayEdge box (accepted_traces_identity accepted memory capacity index box within boxNonzero))

example : check ⟨⟨4, true, [⟨3, .reference⟩], 3⟩, true, 1, 1, 1⟩ = true := by decide
example : check ⟨⟨4, false, [⟨3, .reference⟩], 3⟩, true, 1, 1, 1⟩ = false := by decide
example : check ⟨⟨4, true, [⟨3, .reference⟩], 3⟩, false, 1, 1, 1⟩ = false := by decide
example : check ⟨⟨4, true, [⟨3, .reference⟩], 3⟩, true, 1, 1, 0⟩ = false := by decide
end PystachyCompanion
