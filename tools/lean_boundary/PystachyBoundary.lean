-- SPDX-License-Identifier: MIT
import Std

/-!
# A checked dynamic-payload boundary

This development checks a small, explicit control-flow abstraction of typed IR.
Locations include immutable SSA results and mutable private slots; their values
are abstracted to runtime tags, one per value. It does not formalize Python, the
IR exporter, the abstraction from IR, payload representation, or LLVM lowering.

A guard tests whether a location's tag is one of a finite set of tags, and a
payload read accepts a finite set: the tags whose payloads share the expected
layout (a class's own objects and its subclasses', or an int's and a bool's).

The certificate is an untrusted list of facts at each program point; a fact
confines one location's tag to a finite set. Every transfer and every payload
read is checked independently. In particular, a certificate cannot seed facts at
entry or retain a fact across an incompatible assignment. The theorem quantifies
over all initial tag states, all nondeterministic choices, and every finite
execution, including loops.
-/

namespace PystachyBoundary

abbrev Location := String
abbrev Tag := String
/-- A finite set of tags, as a list: a guard's tested tags or a read's accepted ones. -/
abbrev TagSet := List Tag
/-- `(location, tags)`: the location's current tag is one of `tags`. -/
abbrev Fact := Location × TagSet
abbrev Facts := List Fact
abbrev Certificate := List Facts
abbrev Tags := Location → Tag

inductive Node where
  | copy (dst src : Location) (next : Nat)
  | havoc (dst : Location) (next : Nat)
  | guard (value : Location) (tags : TagSet) (yes no : Nat)
  | choice (yes no : Nat)
  | jump (next : Nat)
  | payload (value : Location) (tags : TagSet) (next : Nat)
  | stop
  deriving Repr, DecidableEq

structure Program where
  nodes : List Node
  entry : Nat := 0
  deriving Repr, DecidableEq

def factsAt (certificate : Certificate) (pc : Nat) : Facts :=
  (certificate[pc]?).getD []

/-- Some fact about `location` confines its tag to `allowed`, counting only the
tags `keep` admits: a guard's outcome rules out the others. -/
def Covered (facts : Facts) (location : Location) (keep : Tag → Bool) (allowed : TagSet) : Prop :=
  ∃ fact ∈ facts, fact.1 = location ∧ ∀ tag ∈ fact.2, keep tag = true → tag ∈ allowed

instance (facts : Facts) (location : Location) (keep : Tag → Bool) (allowed : TagSet) :
    Decidable (Covered facts location keep allowed) := by
  unfold Covered
  infer_instance

/-- Every tag remains possible: no outcome rules one out. -/
def anyTag (_ : Tag) : Bool := true

/-- All facts required at a successor must follow from the predecessor. -/
def EdgeOK (program : Program) (certificate : Certificate) (target : Nat)
    (justified : Fact → Prop) : Prop :=
  target < program.nodes.length ∧ ∀ fact ∈ factsAt certificate target, justified fact

def NodeOK (program : Program) (certificate : Certificate) (pc : Nat) : Node → Prop
  | .copy dst src next =>
      EdgeOK program certificate next (fun fact =>
        Covered (factsAt certificate pc) (if fact.1 = dst then src else fact.1) anyTag fact.2)
  | .havoc dst next =>
      EdgeOK program certificate next (fun fact =>
        fact.1 ≠ dst ∧ Covered (factsAt certificate pc) fact.1 anyTag fact.2)
  | .guard value tags yes no =>
      EdgeOK program certificate yes (fun fact =>
        (fact.1 = value ∧ ∀ tag ∈ tags, tag ∈ fact.2) ∨
        Covered (factsAt certificate pc) fact.1
          (fun tag => decide (fact.1 ≠ value ∨ tag ∈ tags)) fact.2) ∧
      EdgeOK program certificate no (fun fact =>
        Covered (factsAt certificate pc) fact.1
          (fun tag => decide (fact.1 ≠ value ∨ tag ∉ tags)) fact.2)
  | .choice yes no =>
      EdgeOK program certificate yes (fun fact =>
        Covered (factsAt certificate pc) fact.1 anyTag fact.2) ∧
      EdgeOK program certificate no (fun fact =>
        Covered (factsAt certificate pc) fact.1 anyTag fact.2)
  | .jump next =>
      EdgeOK program certificate next (fun fact =>
        Covered (factsAt certificate pc) fact.1 anyTag fact.2)
  | .payload value tags next =>
      Covered (factsAt certificate pc) value anyTag tags ∧
      EdgeOK program certificate next (fun fact =>
        Covered (factsAt certificate pc) fact.1 anyTag fact.2)
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
  | copy {dst src : Location} {next : Nat} {tags : Tags} :
      Move (.copy dst src next) tags next (assign tags dst (tags src))
  | havoc {dst : Location} {next : Nat} {tags : Tags} {arbitraryTag : Tag} :
      Move (.havoc dst next) tags next (assign tags dst arbitraryTag)
  | guardYes {value : Location} {tested : TagSet} {yes no : Nat} {tags : Tags}
      (member : tags value ∈ tested) : Move (.guard value tested yes no) tags yes tags
  | guardNo {value : Location} {tested : TagSet} {yes no : Nat} {tags : Tags}
      (absent : tags value ∉ tested) : Move (.guard value tested yes no) tags no tags
  | choiceYes {yes no : Nat} {tags : Tags} : Move (.choice yes no) tags yes tags
  | choiceNo {yes no : Nat} {tags : Tags} : Move (.choice yes no) tags no tags
  | jump {next : Nat} {tags : Tags} : Move (.jump next) tags next tags
  | payload {value : Location} {accepted : TagSet} {next : Nat} {tags : Tags} :
      Move (.payload value accepted next) tags next tags

def Step (program : Program) (before after : State) : Prop :=
  ∃ node, program.nodes[before.pc]? = some node ∧
    Move node before.tags after.pc after.tags

inductive Reachable (program : Program) (initial : Tags) : State → Prop where
  | entry : Reachable program initial ⟨program.entry, initial⟩
  | step : Reachable program initial before → Step program before after →
      Reachable program initial after

def Knows (tags : Tags) (facts : Facts) : Prop :=
  ∀ fact ∈ facts, tags fact.1 ∈ fact.2

private theorem accepted_node {program : Program} {certificate : Certificate}
    (accepted : Accepted program certificate)
    (found : program.nodes[pc]? = some node) :
    NodeOK program certificate pc node := by
  have bound : pc < program.nodes.length := List.getElem?_eq_some_iff.mp found |>.1
  have obligation := accepted.2.2.2 pc (List.mem_range.mpr bound)
  simpa [found] using obligation

/-- A covering fact confines a location's actual tag whenever `keep` admits it. -/
private theorem covered {tags : Tags} {facts : Facts} {location : Location}
    {keep : Tag → Bool} {allowed : TagSet}
    (known : Knows tags facts) (cover : Covered facts location keep allowed)
    (kept : keep (tags location) = true) : tags location ∈ allowed := by
  obtain ⟨fact, member, same, within⟩ := cover
  have actual := known fact member
  rw [same] at actual
  exact within _ actual kept

private theorem transfer {program : Program} {certificate : Certificate}
    {pc target : Nat} {node : Node} {tags result : Tags}
    (obligation : NodeOK program certificate pc node)
    (known : Knows tags (factsAt certificate pc))
    (move : Move node tags target result) :
    Knows result (factsAt certificate target) := by
  cases move with
  | @copy dst src next =>
      intro fact member
      have justified := obligation.2 fact member
      dsimp only at justified
      split at justified
      next replaced => simpa [assign, replaced] using covered known justified rfl
      next unchanged => simpa [assign, unchanged] using covered known justified rfl
  | havoc =>
      intro fact member
      obtain ⟨unchanged, justified⟩ := obligation.2 fact member
      simpa [assign, unchanged] using covered known justified rfl
  | @guardYes value tested yes no _ inTested =>
      intro fact member
      rcases obligation.1.2 fact member with ⟨same, within⟩ | justified
      · rw [same]
        exact within _ inTested
      · apply covered known justified
        by_cases same : fact.1 = value
        · rw [same]
          exact decide_eq_true (Or.inr inTested)
        · exact decide_eq_true (Or.inl same)
  | @guardNo value tested yes no _ notTested =>
      intro fact member
      have justified := obligation.2.2 fact member
      apply covered known justified
      by_cases same : fact.1 = value
      · rw [same]
        exact decide_eq_true (Or.inr notTested)
      · exact decide_eq_true (Or.inl same)
  | choiceYes =>
      intro fact member
      exact covered known (obligation.1.2 fact member) rfl
  | choiceNo =>
      intro fact member
      exact covered known (obligation.2.2 fact member) rfl
  | jump =>
      intro fact member
      exact covered known (obligation.2 fact member) rfl
  | payload =>
      intro fact member
      exact covered known (obligation.2.2 fact member) rfl

theorem reachable_facts {program : Program} {certificate : Certificate} {initial : Tags}
    (accepted : Accepted program certificate)
    (reachable : Reachable program initial state) :
    Knows state.tags (factsAt certificate state.pc) := by
  induction reachable with
  | entry => simp [Knows, accepted.2.2.1]
  | step _ moved induction =>
      obtain ⟨node, found, move⟩ := moved
      exact transfer (accepted_node accepted found) induction move

/-- Every reachable payload read finds one of the tags it accepts, for all
initial values. This proves tag safety of the normalized program, not its
correspondence to Pystachy or the representation correctness of a runtime
payload operation. -/
theorem accepted_payload_safe {program : Program} {certificate : Certificate}
    {initial : Tags} {state : State} {value : Location} {accepted : TagSet} {next : Nat}
    (checked : check program certificate = true)
    (reachable : Reachable program initial state)
    (projection : program.nodes[state.pc]? = some (.payload value accepted next)) :
    state.tags value ∈ accepted := by
  have valid := (check_iff program certificate).mp checked
  have obligation := (accepted_node valid projection).1
  exact covered (reachable_facts valid reachable) obligation rfl

/- Kernel-reduced regression examples, including an invalidated slot and a
join with an unguarded predecessor. These are not assumed by the theorem. -/
def guarded : Program := ⟨[
  .copy "slot" "argument" 1,
  .copy "observed" "slot" 2,
  .guard "slot" ["float"] 3 5,
  .copy "reload" "slot" 4,
  .payload "reload" ["float"] 5,
  .stop], 0⟩

def guardedCertificate : Certificate := [
  [], [], [], [("slot", ["float"])], [("reload", ["float"])], []]

example : check guarded guardedCertificate = true := by decide

def wrongValue : Program := ⟨[
  .guard "x" ["float"] 1 2, .payload "y" ["float"] 2, .stop], 0⟩

example : check wrongValue [[], [("x", ["float"])], []] = false := by decide
example : check wrongValue [[], [("y", ["float"])], []] = false := by decide

def rebound : Program := ⟨[
  .guard "x" ["float"] 1 3, .copy "x" "y" 2,
  .payload "x" ["float"] 3, .stop], 0⟩

example : check rebound [[], [("x", ["float"])], [("x", ["float"])], []] = false := by decide

def forgotten : Program := ⟨[
  .guard "x" ["float"] 1 3, .havoc "x" 2,
  .payload "x" ["float"] 3, .stop], 0⟩

example : check forgotten [[], [("x", ["float"])], [("x", ["float"])], []] = false := by decide

def unsafeJoin : Program := ⟨[
  .guard "x" ["float"] 1 2, .jump 3, .jump 3,
  .payload "x" ["float"] 4, .stop], 0⟩

example : check unsafeJoin [[], [("x", ["float"])], [], [("x", ["float"])], []] = false := by decide

def circular : Program := ⟨[
  .jump 1, .payload "x" ["float"] 1], 0⟩

example : check circular [[], [("x", ["float"])]] = false := by decide
example : check ⟨[.payload "x" ["float"] 0], 0⟩ [[("x", ["float"])]] = false := by decide
example : check ⟨[.jump 7], 0⟩ [[]] = false := by decide

def guardedLoop : Program := ⟨[
  .guard "x" ["float"] 1 3, .payload "x" ["float"] 2,
  .jump 1, .stop], 0⟩

example : check guardedLoop [[], [("x", ["float"])], [("x", ["float"])], []] = true := by decide

/- A bool's payload is its int value, so an int read accepts either tag; a join
of the two branches keeps both. Accepting only int's tag must fail, as must a
fact that a failed test cannot establish. -/
def intOrBool (accepted : TagSet) : Program := ⟨[
  .guard "x" ["int"] 2 1,
  .guard "x" ["bool"] 2 3,
  .payload "x" accepted 3,
  .stop], 0⟩

example : check (intOrBool ["int", "bool"]) [[], [], [("x", ["int", "bool"])], []] = true := by decide
example : check (intOrBool ["int"]) [[], [], [("x", ["int", "bool"])], []] = false := by decide
example : check (intOrBool ["int"]) [[], [], [("x", ["int"])], []] = false := by decide
example : check (intOrBool ["int", "bool"]) [[], [("x", ["bool"])], [("x", ["int", "bool"])], []] = false := by decide

/- An isinstance test of a class admits its subclasses and None; a failed test
for None then leaves the classes whose payload layout the read accepts. -/
def subclassRead (excludeNone : Bool) : Program := ⟨[
  .guard "x" ["A", "B", "none"] 1 4,
  if excludeNone then .guard "x" ["none"] 4 2 else .jump 2,
  .payload "x" ["A", "B"] 3,
  .stop, .stop], 0⟩

example : check (subclassRead true)
    [[], [("x", ["A", "B", "none"])], [("x", ["A", "B"])], [], []] = true := by decide
example : check (subclassRead false)
    [[], [("x", ["A", "B", "none"])], [("x", ["A", "B"])], [], []] = false := by decide

/- A switch's default arm keeps what no case matched. -/
def caseDefault : Program := ⟨[
  .guard "x" ["A", "B", "C"] 1 5,
  .guard "x" ["A"] 5 2,
  .guard "x" ["B"] 5 3,
  .payload "x" ["C"] 4,
  .stop, .stop], 0⟩

example : check caseDefault
    [[], [("x", ["A", "B", "C"])], [("x", ["B", "C"])], [("x", ["C"])], [], []] = true := by decide
example : check caseDefault
    [[], [("x", ["A", "B", "C"])], [("x", ["C"])], [("x", ["C"])], [], []] = false := by decide

end PystachyBoundary
