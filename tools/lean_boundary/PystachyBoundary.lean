-- SPDX-License-Identifier: MIT
import Std

/-!
# A checked dynamic-payload boundary

This development checks a small, explicit control-flow abstraction of typed IR.
Locations include immutable SSA results and mutable private slots; their values
are abstracted to runtime tags. It does not formalize Python, the IR exporter,
the abstraction from IR, payload representation, or LLVM lowering.

The certificate is an untrusted list of positive tag facts at each program
point. Every transfer and every payload read is checked independently. In
particular, a certificate cannot seed facts at entry or retain a fact across an
incompatible assignment. The theorem quantifies over all initial tag states,
all nondeterministic choices, and every finite execution, including loops.
-/

namespace PystachyBoundary

abbrev Location := String
abbrev Tag := String
abbrev Fact := Location × Tag
abbrev Facts := List Fact
abbrev Certificate := List Facts
abbrev Tags := Location → Tag

inductive Node where
  | copy (dst src : Location) (next : Nat)
  | havoc (dst : Location) (next : Nat)
  | guard (value : Location) (tag : Tag) (yes no : Nat)
  | choice (yes no : Nat)
  | jump (next : Nat)
  | payload (value : Location) (tag : Tag) (next : Nat)
  | stop
  deriving Repr, DecidableEq

structure Program where
  nodes : List Node
  entry : Nat := 0
  deriving Repr, DecidableEq

def factsAt (certificate : Certificate) (pc : Nat) : Facts :=
  (certificate[pc]?).getD []

/-- All facts required at a successor must follow from the predecessor. -/
def EdgeOK (program : Program) (certificate : Certificate) (target : Nat)
    (justified : Fact → Prop) : Prop :=
  target < program.nodes.length ∧ ∀ fact ∈ factsAt certificate target, justified fact

def NodeOK (program : Program) (certificate : Certificate) (pc : Nat) : Node → Prop
  | .copy dst src next =>
      EdgeOK program certificate next (fun fact =>
        if fact.1 = dst then (src, fact.2) ∈ factsAt certificate pc
        else fact ∈ factsAt certificate pc)
  | .havoc dst next =>
      EdgeOK program certificate next (fun fact =>
        fact.1 ≠ dst ∧ fact ∈ factsAt certificate pc)
  | .guard value tag yes no =>
      EdgeOK program certificate yes (fun fact =>
        fact = (value, tag) ∨ fact ∈ factsAt certificate pc) ∧
      EdgeOK program certificate no (fun fact => fact ∈ factsAt certificate pc)
  | .choice yes no =>
      EdgeOK program certificate yes (fun fact => fact ∈ factsAt certificate pc) ∧
      EdgeOK program certificate no (fun fact => fact ∈ factsAt certificate pc)
  | .jump next =>
      EdgeOK program certificate next (fun fact => fact ∈ factsAt certificate pc)
  | .payload value tag next =>
      (value, tag) ∈ factsAt certificate pc ∧
      EdgeOK program certificate next (fun fact => fact ∈ factsAt certificate pc)
  | .stop => True

instance (program : Program) (certificate : Certificate) (target : Nat)
    (justified : Fact → Prop) [DecidablePred justified] :
    Decidable (EdgeOK program certificate target justified) := by
  unfold EdgeOK
  infer_instance

instance (program : Program) (certificate : Certificate) (pc : Nat) (node : Node) :
    Decidable (NodeOK program certificate pc node) := by
  cases node <;> unfold NodeOK <;> infer_instance

/-- Closedness, certificate shape, and every local proof obligation. -/
def Accepted (program : Program) (certificate : Certificate) : Prop :=
  program.entry < program.nodes.length ∧
  certificate.length = program.nodes.length ∧
  factsAt certificate program.entry = [] ∧
  ∀ pc ∈ List.range program.nodes.length,
    match program.nodes[pc]? with
    | some node => NodeOK program certificate pc node
    | none => False

instance (program : Program) (certificate : Certificate) :
    Decidable (Accepted program certificate) := by
  letI : DecidablePred (fun pc => match program.nodes[pc]? with
      | some node => NodeOK program certificate pc node
      | none => False) := fun pc => by
    dsimp only
    split <;> infer_instance
  unfold Accepted
  infer_instance

/-- The executable validator used by the prototype. -/
def check (program : Program) (certificate : Certificate) : Bool :=
  decide (Accepted program certificate)

theorem check_iff (program : Program) (certificate : Certificate) :
    check program certificate = true ↔ Accepted program certificate := by
  simp [check]

/-- Assigning a slot changes its current value, not any previous copied value. -/
def assign (tags : Tags) (dst : Location) (tag : Tag) : Tags :=
  fun location => if location = dst then tag else tags location

structure State where
  pc : Nat
  tags : Tags

/-- Operational rules are independent of the checker and its certificates.
Payload steps deliberately have no safety premise: the theorem must prove it. -/
inductive Move : Node → Tags → Nat → Tags → Prop where
  | copy : Move (.copy dst src next) tags next (assign tags dst (tags src))
  | havoc : Move (.havoc dst next) tags next (assign tags dst arbitraryTag)
  | guardYes (equalTag : tags value = tag) : Move (.guard value tag yes no) tags yes tags
  | guardNo (differs : tags value ≠ tag) : Move (.guard value tag yes no) tags no tags
  | choiceYes : Move (.choice yes no) tags yes tags
  | choiceNo : Move (.choice yes no) tags no tags
  | jump : Move (.jump next) tags next tags
  | payload : Move (.payload value tag next) tags next tags

def Step (program : Program) (before after : State) : Prop :=
  ∃ node, program.nodes[before.pc]? = some node ∧
    Move node before.tags after.pc after.tags

inductive Reachable (program : Program) (initial : Tags) : State → Prop where
  | entry : Reachable program initial ⟨program.entry, initial⟩
  | step : Reachable program initial before → Step program before after →
      Reachable program initial after

def Knows (tags : Tags) (facts : Facts) : Prop :=
  ∀ fact ∈ facts, tags fact.1 = fact.2

private theorem accepted_node {program : Program} {certificate : Certificate}
    (accepted : Accepted program certificate)
    (found : program.nodes[pc]? = some node) :
    NodeOK program certificate pc node := by
  have bound : pc < program.nodes.length := List.getElem?_eq_some_iff.mp found |>.1
  have obligation := accepted.2.2.2 pc (List.mem_range.mpr bound)
  simpa [found] using obligation

private theorem transfer {program : Program} {certificate : Certificate}
    {pc target : Nat} {node : Node} {tags result : Tags}
    (obligation : NodeOK program certificate pc node)
    (known : Knows tags (factsAt certificate pc))
    (move : Move node tags target result) :
    Knows result (factsAt certificate target) := by
  cases move with
  | copy =>
      intro fact member
      have justified := obligation.2 fact member
      dsimp only at justified
      split at justified
      next replaced => simpa [assign, replaced] using known _ justified
      next unchanged => simpa [assign, unchanged] using known _ justified
  | havoc =>
      intro fact member
      obtain ⟨unchanged, justified⟩ := obligation.2 fact member
      simpa [assign, unchanged] using known fact justified
  | guardYes equalTag =>
      intro fact member
      rcases obligation.1.2 fact member with equal | justified
      · subst fact
        exact equalTag
      · exact known fact justified
  | guardNo =>
      intro fact member
      exact known fact (obligation.2.2 fact member)
  | choiceYes =>
      intro fact member
      exact known fact (obligation.1.2 fact member)
  | choiceNo =>
      intro fact member
      exact known fact (obligation.2.2 fact member)
  | jump =>
      intro fact member
      exact known fact (obligation.2 fact member)
  | payload =>
      intro fact member
      exact known fact (obligation.2.2 fact member)

theorem reachable_facts {program : Program} {certificate : Certificate} {initial : Tags}
    (accepted : Accepted program certificate)
    (reachable : Reachable program initial state) :
    Knows state.tags (factsAt certificate state.pc) := by
  induction reachable with
  | entry => simp [Knows, accepted.2.2.1]
  | step _ moved induction =>
      obtain ⟨node, found, move⟩ := moved
      exact transfer (accepted_node accepted found) induction move

/-- Every reachable payload read has the correct tag, for all initial values.
This proves tag safety of the normalized program, not its correspondence to
Pystachy or the representation correctness of a runtime payload operation. -/
theorem accepted_payload_safe {program : Program} {certificate : Certificate}
    {initial : Tags} {state : State} {value : Location} {tag : Tag} {next : Nat}
    (accepted : check program certificate = true)
    (reachable : Reachable program initial state)
    (projection : program.nodes[state.pc]? = some (.payload value tag next)) :
    state.tags value = tag := by
  have accepted' := (check_iff program certificate).mp accepted
  have membership := (accepted_node accepted' projection).1
  exact reachable_facts accepted' reachable (value, tag) membership

/- Kernel-reduced regression examples, including an invalidated slot and a
join with an unguarded predecessor. These are not assumed by the theorem. -/
def guarded : Program := ⟨[
  .copy "slot" "argument" 1,
  .copy "observed" "slot" 2,
  .guard "slot" "float" 3 5,
  .copy "reload" "slot" 4,
  .payload "reload" "float" 5,
  .stop], 0⟩

def guardedCertificate : Certificate := [
  [], [], [], [("slot", "float")], [("reload", "float")], []]

example : check guarded guardedCertificate = true := by decide

def wrongValue : Program := ⟨[
  .guard "x" "float" 1 2, .payload "y" "float" 2, .stop], 0⟩

example : check wrongValue [[], [("x", "float")], []] = false := by decide
example : check wrongValue [[], [("y", "float")], []] = false := by decide

def rebound : Program := ⟨[
  .guard "x" "float" 1 3, .copy "x" "y" 2,
  .payload "x" "float" 3, .stop], 0⟩

example : check rebound [[], [("x", "float")], [("x", "float")], []] = false := by decide

def forgotten : Program := ⟨[
  .guard "x" "float" 1 3, .havoc "x" 2,
  .payload "x" "float" 3, .stop], 0⟩

example : check forgotten [[], [("x", "float")], [("x", "float")], []] = false := by decide

def unsafeJoin : Program := ⟨[
  .guard "x" "float" 1 2, .jump 3, .jump 3,
  .payload "x" "float" 4, .stop], 0⟩

example : check unsafeJoin [[], [("x", "float")], [], [("x", "float")], []] = false := by decide

def circular : Program := ⟨[
  .jump 1, .payload "x" "float" 1], 0⟩

example : check circular [[], [("x", "float")]] = false := by decide
example : check ⟨[.payload "x" "float" 0], 0⟩ [[("x", "float")]] = false := by decide
example : check ⟨[.jump 7], 0⟩ [[]] = false := by decide

def guardedLoop : Program := ⟨[
  .guard "x" "float" 1 3, .payload "x" "float" 2,
  .jump 1, .stop], 0⟩

example : check guardedLoop [[], [("x", "float")], [("x", "float")], []] = true := by decide

end PystachyBoundary
