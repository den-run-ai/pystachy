-- SPDX-License-Identifier: MIT
import PystachyBoundary

/-!
# Promoting-integer storage obligations

The executable guard checker is PystachyBoundary.check. Its tags can describe
more than dynamic Python types: the storage adapter uses independent locations
for a value's fit test, a tuple item's marker test and its digit-pointer test.
The corollaries below connect accepted graph obligations to integer values and
storage accesses. Graph reachability does not assume any read is safe.

This is a model of canonical storage, not a proof that the C runtime implements
it. In particular, a digit pointer is represented by the integer it denotes;
GC/liveness, source-to-IR correspondence and the adapter's interpretation of
guards/layout metadata remain trusted. A marker test alone never establishes
that a plain tuple has a trailing slot. A promoting read contract instead says
that there is a tail or that the word cannot be the marker. The marker guard
then establishes tail existence. All plain-to-promoting view conversions must
justify that contract; a declared type cannot do so by itself.

Complete stack-to-heap tuple copies are a separate storage operation. Their
stack predicate needs an explicit ABI promise about physical extent; an
ordinary promoting read contract or a stack-address test alone is insufficient.
-/

namespace PystachyStorage
open PystachyBoundary

def marker : Int := -9223372036854775808
def Fits (value : Int) : Prop := marker ≤ value ∧ value ≤ 9223372036854775807

instance (value : Int) : Decidable (Fits value) := inferInstanceAs (Decidable (_ ∧ _))

/-- The actual low word is zero, not a truncated value, outside the signed range. -/
def low (value : Int) : Int := if Fits value then value else 0

/-- None models the null digit pointer, not absence of a trailing storage slot. -/
def digits (value : Int) : Option Int := if Fits value then none else some value

def fitTag (value : Int) : Tag := if Fits value then "fit" else "large"
def markerTag (word : Int) : Tag := if word = marker then "marker" else "ordinary"
def digitTag (pointer : Option Int) : Tag := if pointer.isNone then "null" else "digits"

/-- A nullable tuple needs no item conversion on its absent branch. Such a
fit-cell fact means boundary readiness, not that null has an integer payload. -/
def optionalFitTag : Option Int → Tag
  | none => "fit"
  | some value => fitTag value

/-- An ordinary 64-bit tuple has no extra word; a promoting tuple always has it,
including when its item is exactly INT64_MIN and that word holds null. -/
inductive Item where
  | plain (word : Int)
  | promoting (value : Int)
  deriving Repr, DecidableEq

def Item.word : Item → Int
  | .plain word => word
  | .promoting value => if Fits value then value else marker

def Item.tail : Item → Option (Option Int)
  | .plain _ => none
  | .promoting value => some (digits value)

def Item.hasTail : Item → Prop
  | .plain _ => False
  | .promoting _ => True

/-- A promoting view may alias a shorter plain tuple provided its item is not
the marker. It need not promise a tail on an unreachable marker branch. -/
def ReadableAsPromoting (item : Item) : Prop := item.hasTail ∨ item.word ≠ marker

/-- Decoding a promoting view may read the tail only on the marker path.
Outer None is an out-of-layout access; inner None is the valid null pointer. -/
def decode (item : Item) : Option Int :=
  if item.word = marker then item.tail.map (fun pointer => pointer.getD marker)
  else some item.word

theorem low_of_fit {value : Int} (fit : fitTag value = "fit") : low value = value := by
  by_cases h : Fits value
  · simp [low, h]
  · simp [fitTag, h] at fit

theorem promoting_decode (value : Int) : decode (.promoting value) = some value := by
  by_cases h : Fits value
  · by_cases m : value = marker
    · subst value
      simp [decode, Item.word, Item.tail, digits, h]
    · simp [decode, Item.word, h, m]
  · simp [decode, Item.word, Item.tail, digits, h]

theorem plain_view_safe {word : Int} (ordinary : markerTag word = "ordinary") :
    decode (.plain word) = some word := by
  by_cases h : word = marker
  · simp [markerTag, h] at ordinary
  · simp [decode, Item.word, h]

/-- Marker exclusion is necessary too: a plain INT64_MIN tuple cannot be
reinterpreted as a promoting tuple, even though INT64_MIN itself fits. -/
theorem plain_marker_has_no_tail : decode (.plain marker) = none := by
  simp [decode, Item.word, Item.tail]

theorem null_digits_narrow {value : Int} (null : digitTag (digits value) = "null") :
    (.promoting value : Item).word = value ∧ Fits value := by
  by_cases h : Fits value
  · simp [Item.word, h]
  · simp [digitTag, digits, h] at null

/-- These are exactly the two successful branches of a container-slot fit test. -/
theorem slot_fits_iff (value : Int) :
    ((.promoting value : Item).word ≠ marker ∨ digits value = none) ↔ Fits value := by
  by_cases fits : Fits value <;> simp [Item.word, digits, fits]

/-- The canonical pair has Python integer truth even where its low word is zero
for a large value. The pointer-to-word conversion's nullness is an explicit
representation premise; arbitrary pointer bits need no numeric interpretation. -/
theorem pair_truth_zero (value : Int) (lo hi : BitVec 64)
    (low_representation : lo.toInt = low value)
    (pointer_nullness : hi = 0#64 ↔ Fits value) :
    (lo ||| hi) = 0#64 ↔ value = 0 := by
  rw [BitVec.or_eq_zero_iff]
  by_cases fits : Fits value
  · have pointer_zero := pointer_nullness.mpr fits
    have word_zero : lo = 0#64 ↔ value = 0 := by
      rw [← BitVec.toInt_inj]
      simp [low_representation, low, fits]
    simpa [pointer_zero] using word_zero
  · have pointer_nonzero : hi ≠ 0#64 := fun zero => fits (pointer_nullness.mp zero)
    have value_nonzero : value ≠ 0 := by
      intro zero
      subst value
      exact fits (by decide)
    simp [pointer_nonzero, value_nonzero]

theorem layout_has_tail {item : Item} (layout : item.hasTail) :
    ∃ pointer, item.tail = some pointer := by
  cases item with
  | plain word => exact False.elim layout
  | promoting value => exact ⟨digits value, rfl⟩

private theorem accepted_singleton {program : Program} {certificate : Certificate}
    {initial : Tags} {state : State} {location : Location} {tag : Tag} {next : Nat}
    (checked : check program certificate = true)
    (reachable : Reachable program initial state)
    (read : program.nodes[state.pc]? = some (.payload location [tag] next)) :
    state.tags location = tag := by
  have safe := accepted_payload_safe checked reachable read
  simpa using safe

/-- Every reachable checked use of the low word as a number is the full value,
when the adapter faithfully interprets that location's fit predicate. -/
theorem accepted_low_word {program : Program} {certificate : Certificate}
    {initial : Tags} {state : State} {location : Location} {next : Nat} {value : Int}
    (checked : check program certificate = true)
    (reachable : Reachable program initial state)
    (read : program.nodes[state.pc]? = some (.payload location ["fit"] next))
    (interpreted : state.tags location = fitTag value) :
    low value = value := by
  apply low_of_fit
  rw [← interpreted]
  exact accepted_singleton checked reachable read

/-- A checked marker exclusion makes an ordinary tuple's promoting view safe;
the result remains its original 64-bit value without reading any tail slot. -/
theorem accepted_plain_view {program : Program} {certificate : Certificate}
    {initial : Tags} {state : State} {location : Location} {next : Nat} {word : Int}
    (checked : check program certificate = true)
    (reachable : Reachable program initial state)
    (read : program.nodes[state.pc]? = some (.payload location ["ordinary"] next))
    (interpreted : state.tags location = markerTag word) :
    decode (.plain word) = some word := by
  apply plain_view_safe
  rw [← interpreted]
  exact accepted_singleton checked reachable read

/-- Tail reads require both the checked marker path and independently justified
read-layout compatibility. An ordinary tuple is allowed as a promoting view only
where the marker path cannot execute. -/
theorem accepted_tail_read {program : Program} {certificate : Certificate}
    {initial : Tags} {state : State} {location : Location} {next : Nat} {item : Item}
    (checked : check program certificate = true)
    (reachable : Reachable program initial state)
    (read : program.nodes[state.pc]? = some (.payload location ["marker"] next))
    (interpreted : state.tags location = markerTag item.word)
    (layout : ReadableAsPromoting item) :
    item.word = marker ∧ ∃ pointer, item.tail = some pointer := by
  have tag := accepted_singleton checked reachable read
  rw [interpreted] at tag
  have marked : item.word = marker := by
    by_cases h : item.word = marker
    · exact h
    · simp [markerTag, h] at tag
  have tail : item.hasTail := by
    cases layout with
    | inl present => exact present
    | inr ordinary => exact False.elim (ordinary marked)
  exact ⟨marked, layout_has_tail tail⟩

/-- A boundary check on the digit pointer prevents returning the sentinel as
a large integer's numeric value. INT64_MIN remains valid through its null tail. -/
theorem accepted_narrowing {program : Program} {certificate : Certificate}
    {initial : Tags} {state : State} {location : Location} {next : Nat} {value : Int}
    (checked : check program certificate = true)
    (reachable : Reachable program initial state)
    (read : program.nodes[state.pc]? = some (.payload location ["null"] next))
    (interpreted : state.tags location = digitTag (digits value)) :
    (.promoting value : Item).word = value ∧ Fits value := by
  apply null_digits_narrow
  rw [← interpreted]
  exact accepted_singleton checked reachable read

/-- The storage adapter also expresses a slot's narrowing as a fit-cell
obligation: a non-marker word fits directly, and the marker path fits only with
null digits. This corollary uses that fit tag, rather than a digit-pointer tag. -/
theorem accepted_slot_narrowing {program : Program} {certificate : Certificate}
    {initial : Tags} {state : State} {location : Location} {next : Nat} {value : Int}
    (checked : check program certificate = true)
    (reachable : Reachable program initial state)
    (read : program.nodes[state.pc]? = some (.payload location ["fit"] next))
    (interpreted : state.tags location = fitTag value) :
    (.promoting value : Item).word = value ∧ Fits value := by
  have tag := accepted_singleton checked reachable read
  rw [interpreted] at tag
  by_cases fits : Fits value
  · simp [Item.word, fits]
  · simp [fitTag, fits] at tag

/-- A null optional tuple crosses unchanged. On its nonnull path every checked
item still has to fit. The optional item's identity must be the same at guard
and boundary; this theorem does not permit moving facts across rebinding. -/
theorem accepted_optional_slot_narrowing {program : Program} {certificate : Certificate}
    {initial : Tags} {state : State} {location : Location} {next : Nat}
    {item : Option Int}
    (checked : check program certificate = true)
    (reachable : Reachable program initial state)
    (read : program.nodes[state.pc]? = some (.payload location ["fit"] next))
    (interpreted : state.tags location = optionalFitTag item) :
    ∀ value, item = some value → (.promoting value : Item).word = value ∧ Fits value := by
  intro value present
  apply accepted_slot_narrowing checked reachable read
  simpa [present, optionalFitTag] using interpreted

/-- The semantic result of copying every machine word of a fixed-size buffer.
Words include digit pointers and unused padding without interpreting either. -/
def copyWords (count : Nat) (source : List (BitVec 64)) : List (BitVec 64) :=
  source.take count

/-- A complete construction copy can read all its words without marker tests.
This requires the *separate* ABI promise that the exact source pointer, when
classified as stack storage, has the requested physical extent. A parameter's
promoting read contract alone does not provide this premise. The adapter must
also establish that the copied words, order, count and source match copyWords;
this theorem cannot justify altered or incomplete raw stores. -/
theorem accepted_stack_copy {program : Program} {certificate : Certificate}
    {initial : Tags} {state : State} {location : Location} {next count : Nat}
    {source : List (BitVec 64)}
    (checked : check program certificate = true)
    (reachable : Reachable program initial state)
    (read : program.nodes[state.pc]? = some (.payload location ["stack"] next))
    (abiExtent : state.tags location = "stack" → count ≤ source.length) :
    ∀ index, index < count → ∃ word,
      source[index]? = some word ∧ (copyWords count source)[index]? = some word := by
  have tagged : state.tags location = "stack" := by
    simpa using accepted_payload_safe checked reachable read
  intro index within
  have existsAt : index < source.length := Nat.lt_of_lt_of_le within (abiExtent tagged)
  refine ⟨source[index], List.getElem?_eq_getElem existsAt, ?_⟩
  rw [copyWords, List.getElem?_take_of_lt within]
  exact List.getElem?_eq_getElem existsAt

/-- Splitting a large set of obligations need not split execution: erasing a
read obligation leaves its successor and the entire tag state unchanged. -/
def eraseRead : Node → Node
  | .payload _ _ next => .jump next
  | node => node

theorem erase_read_move_iff {node : Node} {tags result : Tags} {next : Nat} :
    Move (eraseRead node) tags next result ↔ Move node tags next result := by
  cases node <;> try exact Iff.rfl
  constructor
  · intro moved
    cases moved
    exact Move.payload
  · intro moved
    cases moved
    exact Move.jump

/-- Node IDs, control-flow targets and entry are unchanged. Only the selected
read obligations remain; all other reads become jumps to the same successor. -/
def ReadProjection (original projected : Program) (keep : Nat → Bool) : Prop :=
  projected.entry = original.entry ∧
  ∀ pc, projected.nodes[pc]? = (original.nodes[pc]?).map
    (fun node => if keep pc then node else eraseRead node)

private theorem projected_step {original projected : Program} {keep : Nat → Bool}
    (projection : ReadProjection original projected keep)
    (step : Step original before after) : Step projected before after := by
  obtain ⟨node, found, moved⟩ := step
  refine ⟨if keep before.pc then node else eraseRead node, ?_, ?_⟩
  · rw [projection.2, found]
    rfl
  · split
    · exact moved
    · exact erase_read_move_iff.mpr moved

theorem projected_reachable {original projected : Program} {keep : Nat → Bool}
    {initial : Tags} {state : State}
    (projection : ReadProjection original projected keep)
    (reachable : Reachable original initial state) : Reachable projected initial state := by
  induction reachable with
  | entry =>
      have start : Reachable projected initial ⟨projected.entry, initial⟩ := .entry
      simpa [projection.1] using start
  | step _ moved induction => exact .step induction (projected_step projection moved)

/-- Every original read retained in an accepted batch is safe on every original
execution. Running this for each read's batch covers the complete inventory;
the other read obligations need not already be assumed safe. -/
theorem accepted_projected_payload {original projected : Program} {keep : Nat → Bool}
    {certificate : Certificate} {initial : Tags} {state : State}
    {location : Location} {tags : TagSet} {next : Nat}
    (projection : ReadProjection original projected keep)
    (checked : check projected certificate = true)
    (reachable : Reachable original initial state)
    (read : original.nodes[state.pc]? = some (.payload location tags next))
    (retained : keep state.pc = true) : state.tags location ∈ tags := by
  apply accepted_payload_safe (next := next) checked (projected_reachable projection reachable)
  rw [projection.2, read]
  simp [retained]

/- Kernel-reduced examples exercise actual encodings and graph failure modes. -/
example : low 9223372036854775808 = 0 := by decide
example : low marker = marker := by decide
example : decode (.promoting marker) = some marker := by decide
example : decode (.plain marker) = none := by decide
example : decode (.promoting 9223372036854775808) = some 9223372036854775808 := by decide
example : digitTag (digits marker) = "null" := by decide
example : digitTag (digits 9223372036854775808) = "digits" := by decide
example : (copyWords 2 [0#64, 123#64, 456#64])[1]? = some 123#64 := by decide

def fitUse (tested used : Location) : Program := ⟨[
  .guard tested ["fit"] 1 2, .payload used ["fit"] 2, .stop], 0⟩

example : check (fitUse "fit:x" "fit:x") [[], [("fit:x", ["fit"])], []] = true := by decide
example : check (fitUse "fit:x" "fit:y") [[], [("fit:y", ["fit"])], []] = false := by decide

def stackCopy (tested copied : Location) : Program := ⟨[
  .guard tested ["stack"] 1 2, .payload copied ["stack"] 2, .stop], 0⟩

example : check (stackCopy "stack:x" "stack:x") [[], [("stack:x", ["stack"])], []] = true := by decide
example : check (stackCopy "stack:x" "stack:y") [[], [("stack:y", ["stack"])], []] = false := by decide

def joinedUse : Program := ⟨[
  .guard "fit:x" ["fit"] 1 2, .jump 3, .jump 3,
  .payload "fit:x" ["fit"] 4, .stop], 0⟩

example : check joinedUse [[], [("fit:x", ["fit"])], [], [("fit:x", ["fit"])], []] = false := by decide
example : check ⟨[.jump 1, .payload "fit:x" ["fit"] 1], 0⟩
    [[], [("fit:x", ["fit"])]] = false := by decide

/-- The exception edge must also justify a fact; a failed fit check cannot
reach a numeric use through a handler that joins its success path. -/
def exceptionBypass : Program := ⟨[
  .guard "fit:x" ["fit"] 1 2, .jump 3,
  .choice 3 4, .payload "fit:x" ["fit"] 4, .stop], 0⟩

example : check exceptionBypass
    [[], [("fit:x", ["fit"])], [], [("fit:x", ["fit"])], []] = false := by decide

def markerRead : Program := ⟨[
  .guard "item:x:0" ["marker"] 1 2,
  .payload "item:x:0" ["marker"] 2, .stop], 0⟩

example : check markerRead [[], [("item:x:0", ["marker"])], []] = true := by decide
example : check markerRead [[], [("item:x:1", ["marker"])], []] = false := by decide
example : check ⟨[.jump 1, .payload "item:x:0" ["marker"] 2, .stop], 0⟩
    [[], [("item:x:0", ["marker"])], []] = false := by decide

end PystachyStorage
