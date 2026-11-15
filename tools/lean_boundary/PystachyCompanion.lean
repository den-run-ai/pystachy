-- SPDX-License-Identifier: MIT
import PystachyAlias

/-! A bounded, initialized numeric-list companion. The C adapter supplies the
scanned header transfer, scanned array allocations, setter/getter word offsets
and reserve/slice copy extents. Arbitrary other cells are retained in the model.
Materialization, allocation-time liveness, machine-integer capacity arithmetic,
the concrete collector and the C-to-model adapter are not verified here. -/
namespace PystachyCompanion
open PystachyAlias

structure Copy where
  arrayScanned : Bool
  allocationPrefix : Nat
  sourceOffset : Nat
  targetOffset : Nat
  copyExtra : Nat
  deriving Repr, DecidableEq

structure Contract where
  header : Transfer
  arrayScanned : Bool
  prefixWords : Nat
  storeOffset : Nat
  readOffset : Nat
  growth : Copy
  slice : Copy
  deriving Repr, DecidableEq

def StoreAccepted (contract : Contract) : Prop :=
  PystachyAlias.Accepted contract.header ∧ contract.arrayScanned = true ∧
  0 < contract.prefixWords ∧ contract.storeOffset = contract.prefixWords ∧
  contract.readOffset = contract.storeOffset

def CopyAccepted (copy : Copy) (prefixWords : Nat) : Prop :=
  copy.arrayScanned = true ∧ copy.allocationPrefix = prefixWords ∧
  copy.sourceOffset = copy.targetOffset ∧ copy.targetOffset + copy.copyExtra = prefixWords

def Accepted (contract : Contract) : Prop :=
  StoreAccepted contract ∧ CopyAccepted contract.growth contract.prefixWords ∧
  CopyAccepted contract.slice contract.prefixWords

instance (contract : Contract) : Decidable (Accepted contract) := by
  unfold Accepted StoreAccepted CopyAccepted
  infer_instance

def check (contract : Contract) : Bool := decide (Accepted contract)

def store (memory : Nat → Nat) (word value : Nat) : Nat → Nat :=
  fun address => if address = word then value else memory address

/-- A store and subsequent load preserve the original box address, for arbitrary
other cells. The initialized, stable companion is a precondition. -/
theorem accepted_identity_roundtrip {contract : Contract}
    (accepted : check contract = true) (memory : Nat → Nat) (index box : Nat) :
    store memory (index + contract.storeOffset) box (index + contract.readOffset) = box := by
  have valid : StoreAccepted contract := (of_decide_eq_true accepted : Accepted contract).1
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
  have valid : StoreAccepted contract := (of_decide_eq_true accepted : Accepted contract).1
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
  have valid : StoreAccepted contract := (of_decide_eq_true accepted : Accepted contract).1
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
  have valid : StoreAccepted contract := (of_decide_eq_true accepted : Accepted contract).1
  have headerChecked : PystachyAlias.check contract.header = true := decide_eq_true valid.1
  exact .step (.step (.step .root
    (outerEdge list (accepted_traces_reference outerAccepted 0 list listNonzero)))
    (headerEdge companion (accepted_traces_reference headerChecked 0 companion companionNonzero)))
    (arrayEdge box (accepted_traces_identity accepted memory capacity index box within boxNonzero))

def selectedCopy (contract : Contract) (growth : Bool) : Copy :=
  if growth then contract.growth else contract.slice

private theorem selected_copy_accepted {contract : Contract}
    (accepted : check contract = true) (growth : Bool) :
    CopyAccepted (selectedCopy contract growth) contract.prefixWords := by
  have valid : Accepted contract := of_decide_eq_true accepted
  cases growth with
  | false => exact valid.2.2
  | true => exact valid.2.1

/-- A fresh destination gets exactly the specified source span. Source memory
remains unchanged; allocator freshness and memcpy semantics are explicit runtime
premises of the C adapter, not facts inferred from source pointer inequality. -/
def copySpan (source destination : Nat → Nat) (sourceStart targetStart words : Nat) : Nat → Nat :=
  fun address => if targetStart ≤ address ∧ address - targetStart < words
    then source (sourceStart + (address - targetStart)) else destination address

/-- Both reserve (copy the kind word and all live identities) and a contiguous
slice (copy only the selected identities after the destination's kind word)
preserve every item address. The quantifiers include arbitrary lengths and
arbitrary contents in both memories. -/
theorem accepted_copy_identity {contract : Contract}
    (accepted : check contract = true) (growth : Bool) (source destination : Nat → Nat)
    (begin length index : Nat) (within : index < length) :
    let copy := selectedCopy contract growth
    copySpan source destination (begin + copy.sourceOffset) copy.targetOffset
      (length + copy.copyExtra) (index + contract.prefixWords) =
      source (begin + index + contract.prefixWords) := by
  have valid := selected_copy_accepted accepted growth
  dsimp
  unfold copySpan
  have lower : (selectedCopy contract growth).targetOffset ≤ index + contract.prefixWords := by
    have := valid.2.2.2
    omega
  have upper : index + contract.prefixWords - (selectedCopy contract growth).targetOffset <
      length + (selectedCopy contract growth).copyExtra := by
    have := valid.2.2.2
    omega
  rw [ite_eq_left ⟨lower, upper⟩]
  congr 1
  have := valid.2.2.1
  omega

/-- A copied identity is still a scanned word of the new allocation. The
successful operation's length/capacity invariants and nonoverflowing C extents
are prerequisites; this does not prove that a collection during allocation
preserves a source held only in machine registers. -/
theorem accepted_copy_traces_identity {contract : Contract}
    (accepted : check contract = true) (growth : Bool) (source destination : Nat → Nat)
    (begin length capacity index : Nat) (within : index < length) (fits : length ≤ capacity)
    (nonnull : source (begin + index + contract.prefixWords) ≠ 0) :
    let copy := selectedCopy contract growth
    tracesArray copy.arrayScanned (capacity + copy.allocationPrefix)
      (copySpan source destination (begin + copy.sourceOffset) copy.targetOffset
        (length + copy.copyExtra)) (source (begin + index + contract.prefixWords)) := by
  have valid := selected_copy_accepted accepted growth
  refine ⟨nonnull, valid.1, index + contract.prefixWords, ?_, ?_⟩
  · rw [valid.2.1]
    omega
  · exact accepted_copy_identity accepted growth source destination begin length index within

/-- After the new array is attached, the same header/array chain reaches each
copied identity. For reserve the header is the original list (and all its
aliases); for slicing it is the fresh result. -/
theorem accepted_copied_root_chain {contract : Contract}
    (accepted : check contract = true) (growth : Bool) (source destination : Nat → Nat)
    (begin length capacity index list companion : Nat) (edges : Nat → Nat → Prop)
    (within : index < length) (fits : length ≤ capacity) (companionNonzero : companion ≠ 0)
    (boxNonzero : source (begin + index + contract.prefixWords) ≠ 0)
    (headerEdge : ∀ target, traces contract.header 0 companion target → edges list target)
    (arrayEdge : ∀ target, let copy := selectedCopy contract growth
      tracesArray copy.arrayScanned (capacity + copy.allocationPrefix)
        (copySpan source destination (begin + copy.sourceOffset) copy.targetOffset
          (length + copy.copyExtra)) target → edges companion target) :
    Reachable edges list (source (begin + index + contract.prefixWords)) := by
  have valid : StoreAccepted contract := (of_decide_eq_true accepted : Accepted contract).1
  have headerChecked : PystachyAlias.check contract.header = true := decide_eq_true valid.1
  exact .step (.step .root
    (headerEdge companion (accepted_traces_reference headerChecked 0 companion companionNonzero)))
    (arrayEdge _ (accepted_copy_traces_identity accepted growth source destination begin length
      capacity index within fits boxNonzero))

private def sample : Contract :=
  ⟨⟨4, true, [⟨3, .reference⟩], 3⟩, true, 1, 1, 1,
    ⟨true, 1, 0, 0, 1⟩, ⟨true, 1, 1, 1, 0⟩⟩

example : check sample = true := by decide
example : check {sample with header.scanned := false} = false := by decide
example : check {sample with arrayScanned := false} = false := by decide
example : check {sample with readOffset := 0} = false := by decide
example : check {sample with growth.arrayScanned := false} = false := by decide
example : check {sample with growth.copyExtra := 0} = false := by decide
example : check {sample with slice.sourceOffset := 0} = false := by decide
end PystachyCompanion
