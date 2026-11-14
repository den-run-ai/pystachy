-- SPDX-License-Identifier: MIT
import Std

/-! A bounded reference-box transfer. The runtime adapter derives the allocation,
stores and read offset from the C AST, C layout and actual payload lowering.
This proves address/alias preservation and a tracing edge, not collector safety
or the fidelity of that adapter. -/
namespace PystachyAlias

inductive Source where
  | zero | tag | reference
  deriving Repr, DecidableEq

structure Store where
  word : Nat
  source : Source
  deriving Repr, DecidableEq

structure Transfer where
  words : Nat
  scanned : Bool
  stores : List Store
  readWord : Nat
  deriving Repr, DecidableEq

/-- Stores execute in order; a later conflicting store must not be hidden. -/
def contents (transfer : Transfer) : List Source :=
  transfer.stores.foldl (fun memory store => memory.set store.word store.source)
    (List.replicate transfer.words .zero)

def Accepted (transfer : Transfer) : Prop :=
  transfer.scanned = true ∧ transfer.readWord < transfer.words ∧
  (∀ store ∈ transfer.stores, store.word < transfer.words) ∧
  (contents transfer)[transfer.readWord]? = some .reference

instance (transfer : Transfer) : Decidable (Accepted transfer) := by
  unfold Accepted
  infer_instance

def check (transfer : Transfer) : Bool := decide (Accepted transfer)

def evaluate (tag reference : Nat) : Source → Nat
  | .zero => 0
  | .tag => tag
  | .reference => reference

def read (transfer : Transfer) (tag reference : Nat) : Option Nat :=
  ((contents transfer)[transfer.readWord]?).map (evaluate tag reference)

/-- Every input address is preserved, not merely an equal object's value. -/
theorem accepted_reference_roundtrip {transfer : Transfer}
    (accepted : check transfer = true) (tag reference : Nat) :
    read transfer tag reference = some reference := by
  have valid : Accepted transfer := of_decide_eq_true accepted
  simp [read, valid.2.2.2, evaluate]

/-- Heap mutation through the recovered address is the same mutation through
the original alias. The theorem does not assume the heap contents are immutable. -/
theorem accepted_alias_write {transfer : Transfer}
    (accepted : check transfer = true) (tag reference value : Nat) (heap : Nat → Nat) :
    (fun address => if address = (read transfer tag reference).getD 0 then value else heap address) =
    (fun address => if address = reference then value else heap address) := by
  rw [accepted_reference_roundtrip accepted]
  rfl

/-- The abstract tracer follows every word in a scanned allocation. -/
def traces (transfer : Transfer) (tag reference target : Nat) : Prop :=
  target ≠ 0 ∧ transfer.scanned = true ∧
  ∃ word ∈ contents transfer, evaluate tag reference word = target

theorem accepted_traces_reference {transfer : Transfer}
    (accepted : check transfer = true) (tag reference : Nat) (nonnull : reference ≠ 0) :
    traces transfer tag reference reference := by
  have valid : Accepted transfer := of_decide_eq_true accepted
  refine ⟨nonnull, valid.1, .reference, ?_, rfl⟩
  exact List.mem_of_getElem? valid.2.2.2

inductive Reachable (edges : Nat → Nat → Prop) (root : Nat) : Nat → Prop where
  | root : Reachable edges root root
  | step {parent child : Nat} : Reachable edges root parent → edges parent child →
      Reachable edges root child

/-- Rooting the box retains the original reference in the tracing model. Any
existing downstream edge (for example a list's companion) remains reachable. -/
theorem accepted_root_chain {transfer : Transfer} (accepted : check transfer = true)
    (tag reference box child : Nat) (edges : Nat → Nat → Prop)
    (nonnull : reference ≠ 0)
    (boxEdge : ∀ target, traces transfer tag reference target → edges box target)
    (childEdge : edges reference child) : Reachable edges box child := by
  exact .step (.step .root (boxEdge reference (accepted_traces_reference accepted tag reference nonnull))) childEdge

example : check ⟨2, true, [⟨0, .tag⟩, ⟨1, .reference⟩], 1⟩ = true := by decide
example : check ⟨2, false, [⟨0, .tag⟩, ⟨1, .reference⟩], 1⟩ = false := by decide
example : check ⟨2, true, [⟨0, .tag⟩, ⟨1, .reference⟩, ⟨1, .zero⟩], 1⟩ = false := by decide
example : check ⟨1, true, [⟨0, .tag⟩, ⟨1, .reference⟩], 1⟩ = false := by decide
example : check ⟨2, true, [⟨0, .tag⟩, ⟨1, .reference⟩], 0⟩ = false := by decide
end PystachyAlias
