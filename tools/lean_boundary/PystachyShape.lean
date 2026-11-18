-- SPDX-License-Identifier: MIT
import Std

/-! The shape of a typed-IR function against the compiler's operation table
(`OPS`, src/pystachy_compiler/specs.py): each instruction has the operand,
result and label counts and only the immediates its entry declares, each block
ends in its one terminator, labels name blocks, and each value number has one
definition that every use can name. This is a structural model. It proves no
dominance, typing, effect or lowering property. -/
namespace PystachyShape

/-- How many labels an operation holds. -/
inductive Labels where
  | between (lo hi : Nat)
  | invoke      -- none, or two once an exception edge makes the call an invoke
  | perOperand  -- one for each operand: a phi's predecessors, a switch's cases
  deriving BEq, DecidableEq, Repr

/-- One row of the operation table. -/
structure Spec where
  terminator : Bool
  entry : Bool            -- entry storage: held by a function's slots, never by a block
  operandsMin : Nat
  operandsMax : Option Nat
  results : Option Nat    -- none: a call's, by its signature (none or one)
  labels : Labels
  fields : Nat            -- which of type (1), text (2), immediate (4), descriptor (8) it may set
  deriving BEq, DecidableEq, Repr

/-- An operand's closed kind: a value (0), a parameter (1), a slot (2) or a constant (3). -/
structure Operand where
  kind : Nat
  number : Nat
  deriving BEq, DecidableEq, Repr

structure Ins where
  op : Nat                -- its row of the table
  operands : List Operand
  results : List Nat
  labels : List Nat       -- interned block labels
  implicit : List Nat     -- a check's error block
  fields : Nat            -- which fields it sets, as `Spec.fields`
  joins : Bool            -- a phi: its labels are predecessors, not targets
  deriving BEq, DecidableEq, Repr

structure Block where
  label : Nat
  code : List Ins
  deriving BEq, DecidableEq, Repr

structure Fn where
  params : Nat
  slots : List Ins
  blocks : List Block
  deriving BEq, DecidableEq, Repr

abbrev Table := Array Spec

def LabelCount (rule : Labels) (operands labels : Nat) : Prop :=
  match rule with
  | .between lo hi => lo ≤ labels ∧ labels ≤ hi
  | .invoke => labels = 0 ∨ labels = 2
  | .perOperand => labels = operands

instance (rule : Labels) (operands labels : Nat) : Decidable (LabelCount rule operands labels) := by
  unfold LabelCount; split <;> infer_instance

/-- An instruction has the counts and fields its row declares. -/
def SpecShape (spec : Spec) (inSlots : Bool) (i : Ins) : Prop :=
  spec.entry = inSlots ∧
  spec.operandsMin ≤ i.operands.length ∧
  (match spec.operandsMax with | none => True | some hi => i.operands.length ≤ hi) ∧
  (match spec.results with | none => i.results.length ≤ 1 | some n => i.results.length = n) ∧
  LabelCount spec.labels i.operands.length i.labels.length ∧
  i.fields &&& spec.fields = i.fields ∧
  ∀ a ∈ i.operands, a.kind ≤ 3

instance (spec : Spec) (inSlots : Bool) (i : Ins) : Decidable (SpecShape spec inSlots i) := by
  unfold SpecShape
  cases spec.operandsMax <;> cases spec.results <;> infer_instance

/-- The registry is closed: an instruction names a row, and has its shape. -/
def InsShape (table : Table) (inSlots : Bool) (i : Ins) : Prop :=
  match table[i.op]? with
  | none => False
  | some spec => SpecShape spec inSlots i

instance (table : Table) (inSlots : Bool) (i : Ins) : Decidable (InsShape table inSlots i) := by
  unfold InsShape; split <;> infer_instance

/-- An instruction ends its block: a terminator, or a call with an exception edge. -/
def terminates (table : Table) (i : Ins) : Bool :=
  match table[i.op]? with
  | none => false
  | some spec => spec.terminator || (spec.labels == .invoke && i.labels.length == 2)

/-- A block is its instructions, none of which ends it, and then the one that does. -/
def BlockShape (table : Table) (b : Block) : Prop :=
  ∃ body last, b.code = body ++ [last] ∧ terminates table last = true ∧
    ∀ i ∈ body, terminates table i = false

def checkBlock (table : Table) (b : Block) : Bool :=
  match b.code.getLast? with
  | none => false
  | some last => terminates table last && b.code.dropLast.all (fun i => !terminates table i)

theorem checkBlock_sound (table : Table) (b : Block) (accepted : checkBlock table b = true) :
    BlockShape table b := by
  unfold checkBlock at accepted
  split at accepted
  · contradiction
  · rename_i last found
    obtain ⟨body, split⟩ := List.getLast?_eq_some_iff.mp found
    simp only [Bool.and_eq_true, List.all_eq_true, Bool.not_eq_true'] at accepted
    refine ⟨body, last, split, accepted.1, ?_⟩
    intro i member
    apply accepted.2
    simp [split, member]

/-- Strictly ascending neighbours: a linear test of a sorted list. -/
def ascending : List Nat → Bool
  | [] => true
  | [_] => true
  | a :: b :: rest => a < b && ascending (b :: rest)

theorem ascending_tail (a : Nat) (l : List Nat) (sorted : ascending (a :: l) = true) :
    ascending l = true := by
  cases l with
  | nil => rfl
  | cons b rest => simp [ascending] at sorted; exact sorted.2

theorem ascending_above (a : Nat) (l : List Nat) (sorted : ascending (a :: l) = true) :
    ∀ x ∈ l, a < x := by
  induction l generalizing a with
  | nil => intro x member; cases member
  | cons b rest step =>
      simp [ascending] at sorted
      intro x member
      cases member with
      | head => exact sorted.1
      | tail _ later => exact Nat.lt_trans sorted.1 (step b sorted.2 x later)

theorem ascending_nodup (l : List Nat) (sorted : ascending l = true) : l.Nodup := by
  induction l with
  | nil => exact List.nodup_nil
  | cons a rest step =>
      refine List.nodup_cons.mpr ⟨?_, step (ascending_tail a rest sorted)⟩
      intro member
      exact Nat.lt_irrefl a (ascending_above a rest sorted a member)

/-- No number occurs twice: sorted, then compared with its neighbour. -/
def distinct (l : List Nat) : Bool := ascending (l.mergeSort (fun a b => a ≤ b))

theorem distinct_sound (l : List Nat) (accepted : distinct l = true) : l.Nodup :=
  (List.mergeSort_perm l _).nodup_iff.mp (ascending_nodup _ accepted)

/-- Every number of `uses` is one of `defs`. -/
def covers (defs uses : List Nat) : Bool :=
  let known := Std.HashSet.ofList defs
  uses.all (fun x => known.contains x)

theorem covers_sound (defs uses : List Nat) (accepted : covers defs uses = true) :
    ∀ x ∈ uses, x ∈ defs := by
  intro x member
  simp only [covers, List.all_eq_true] at accepted
  have found := accepted x member
  rw [Std.HashSet.contains_ofList] at found
  simpa using found

def blockResults (f : Fn) : List Nat := f.blocks.flatMap (fun b => b.code.flatMap (·.results))
def slotNumbers (f : Fn) : List Nat := f.slots.flatMap (·.results)
def blockLabels (f : Fn) : List Nat := f.blocks.map (·.label)
def operands (f : Fn) : List Operand := f.blocks.flatMap (fun b => b.code.flatMap (·.operands))
def uses (kind : Nat) (f : Fn) : List Nat := ((operands f).filter (·.kind == kind)).map (·.number)
def named (f : Fn) : List Nat := f.blocks.flatMap (fun b => b.code.flatMap (fun i => i.labels ++ i.implicit))
def targets (f : Fn) : List Nat :=
  f.blocks.flatMap (fun b => b.code.flatMap (fun i => if i.joins then [] else i.labels ++ i.implicit))
def entryLabel (f : Fn) : Option Nat := f.blocks.head?.map (·.label)

/-- What the linear scans decide: each instruction's shape, each parameter an
operand names, and that no branch goes back to the entry block. -/
def LocalShape (table : Table) (f : Fn) : Prop :=
  (∀ i ∈ f.slots, InsShape table true i) ∧
  (∀ b ∈ f.blocks, ∀ i ∈ b.code, InsShape table false i) ∧
  (∀ x ∈ uses 1 f, x < f.params) ∧
  (∀ l ∈ targets f, some l ≠ entryLabel f)

instance (table : Table) (f : Fn) : Decidable (LocalShape table f) := by
  unfold LocalShape; infer_instance

/-- A well-formed function: shaped instructions, terminated blocks, named
labels, and one definition for each value number that an operand reads. -/
structure WellFormed (table : Table) (f : Fn) : Prop where
  shaped : LocalShape table f
  terminated : ∀ b ∈ f.blocks, BlockShape table b
  labelled : (blockLabels f).Nodup
  resolved : ∀ l ∈ named f, l ∈ blockLabels f
  singleDefinition : (blockResults f).Nodup
  defined : ∀ x ∈ uses 0 f, x ∈ blockResults f
  stored : ∀ x ∈ uses 2 f, x ∈ slotNumbers f

def checkFn (table : Table) (f : Fn) : Bool :=
  decide (LocalShape table f) && f.blocks.all (checkBlock table) &&
  distinct (blockLabels f) && covers (blockLabels f) (named f) &&
  distinct (blockResults f) && covers (blockResults f) (uses 0 f) &&
  covers (slotNumbers f) (uses 2 f)

theorem accepted_wellFormed (table : Table) (f : Fn) (accepted : checkFn table f = true) :
    WellFormed table f := by
  simp only [checkFn, Bool.and_eq_true, decide_eq_true_eq, List.all_eq_true] at accepted
  obtain ⟨⟨⟨⟨⟨⟨shaped, terminated⟩, labelled⟩, resolved⟩, single⟩, defined⟩, stored⟩ := accepted
  exact {
    shaped := shaped
    terminated := fun b member => checkBlock_sound table b (terminated b member)
    labelled := distinct_sound _ labelled
    resolved := covers_sound _ _ resolved
    singleDefinition := distinct_sound _ single
    defined := covers_sound _ _ defined
    stored := covers_sound _ _ stored }

/-- An accepted function defines no value number in two instructions' results,
or twice in one: two positions of its results that hold one number are one position. -/
theorem accepted_single_definition (table : Table) (f : Fn) (accepted : checkFn table f = true)
    (i j : Nat) (hi : i < (blockResults f).length) (hj : j < (blockResults f).length)
    (same : (blockResults f)[i] = (blockResults f)[j]) : i = j :=
  (accepted_wellFormed table f accepted).singleDefinition.eq_of_getElem_eq hi hj same

/-- In an accepted function, an instruction that ends a block is that block's last. -/
theorem accepted_terminator_last (table : Table) (f : Fn) (accepted : checkFn table f = true)
    (b : Block) (member : b ∈ f.blocks) :
    ∃ body last, b.code = body ++ [last] ∧ terminates table last = true ∧
      ∀ i ∈ body, terminates table i = false :=
  (accepted_wellFormed table f accepted).terminated b member

end PystachyShape
