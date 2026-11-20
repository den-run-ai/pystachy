-- SPDX-License-Identifier: MIT
import Std
import PystachyShape

/-! Def-before-use for typed-IR functions (the model of `PystachyShape`): on every path from the
entry block to an instruction, the instruction that defines a value it reads has already run.

The adapter claims each block's immediate dominator. The checker trusts none of that claim: it
holds every edge of a block it reaches to the claimed tree (the edge's head has a parent that
is an ancestor of the edge's tail), which makes each claimed ancestor of a block lie on every
path to it (`walk_dominated`). Each read is then checked against its definition: earlier in its
block, or in a block that is a proper ancestor. An invoke's results are first seen at the start
of its normal successor, every edge into which, even from code no path reaches, must come from
the invoke's block. A phi's operand is read at the end of the predecessor its label names. Code
no path reaches is not checked. This is a structural model: it proves nothing of types, effects
or lowering. -/
namespace PystachyDominance
open PystachyShape

/-- A block's successors: what its instructions branch to, a check's error block among them;
not a phi's labels, which name its predecessors. -/
def successors (b : Block) : List Nat :=
  b.code.flatMap (fun i => if i.joins then [] else i.labels ++ i.implicit)

/-- An edge of the function's control-flow graph. -/
def Edge (f : Fn) (u v : Nat) : Prop := ∃ b ∈ f.blocks, b.label = u ∧ v ∈ successors b

/-- `Walk f v trace`: `trace` is the blocks of a path from the entry block to `v`, in order. -/
inductive Walk (f : Fn) : Nat → List Nat → Prop
  | start {e : Nat} : entryLabel f = some e → Walk f e [e]
  | step {u v : Nat} {trace : List Nat} : Walk f u trace → Edge f u v → Walk f v (trace ++ [v])

/-- The claimed dominator tree: each block's immediate dominator, by label. -/
abbrev Tree := Std.HashMap Nat Nat

/-- `Anc t d v`: `d` is `v` or one of its ancestors in `t`. -/
inductive Anc (t : Tree) : Nat → Nat → Prop
  | refl (v : Nat) : Anc t v v
  | up {d v p : Nat} : t[v]? = some p → Anc t d p → Anc t d v

theorem anc_trans {t : Tree} {d p u : Nat} (above : Anc t d p) (below : Anc t p u) : Anc t d u := by
  induction below with
  | refl => exact above
  | up parent _ step => exact Anc.up parent step

/-- Whether `d` is `v` or an ancestor of it, following at most `fuel` parents. -/
def isAnc (t : Tree) (d : Nat) : Nat → Nat → Bool
  | 0, v => d == v
  | fuel + 1, v => d == v || match t[v]? with
      | some p => isAnc t d fuel p
      | none => false

theorem isAnc_sound (t : Tree) (d : Nat) : ∀ fuel v, isAnc t d fuel v = true → Anc t d v := by
  intro fuel
  induction fuel with
  | zero =>
      intro v found
      simp only [isAnc, beq_iff_eq] at found
      subst found
      exact Anc.refl d
  | succ n step =>
      intro v found
      simp only [isAnc, Bool.or_eq_true, beq_iff_eq] at found
      rcases found with same | above
      · subst same
        exact Anc.refl d
      · split at above
        · rename_i p parent
          exact Anc.up parent (step p above)
        · contradiction

/-- A block the claimed tree holds: the entry block, or one that names its parent. -/
def inTree (f : Fn) (t : Tree) (v : Nat) : Bool := entryLabel f == some v || (t[v]?).isSome

/-- Enough parents to follow for any ancestor in a tree of the function's blocks. -/
def fuel (f : Fn) : Nat := f.blocks.length + 1

/-- Whether `d` is a proper ancestor of `v`: an ancestor of its parent. -/
def isProper (f : Fn) (t : Tree) (d v : Nat) : Bool :=
  match t[v]? with
  | some p => isAnc t d (fuel f) p
  | none => false

/-- The entry block has no parent, and every edge out of a block of the tree goes to a block
whose parent is an ancestor of the edge's tail. -/
def treeOk (f : Fn) (t : Tree) : Bool :=
  (match entryLabel f with
   | some e => (t[e]?).isNone
   | none => false) &&
  f.blocks.all fun b => !inTree f t b.label || (successors b).all fun v =>
    match t[v]? with
    | some p => isAnc t p (fuel f) b.label
    | none => false

theorem proper_anc {f : Fn} {t : Tree} {d v : Nat} (found : isProper f t d v = true) : Anc t d v := by
  unfold isProper at found
  split at found
  · rename_i p parent
    exact Anc.up parent (isAnc_sound t d _ _ found)
  · contradiction

/-- Every block on a path from the entry block is in the tree, and each of its ancestors there
lies on that path. -/
theorem walk_dominated (f : Fn) (t : Tree) (ok : treeOk f t = true) {v : Nat} {trace : List Nat}
    (walk : Walk f v trace) : inTree f t v = true ∧ ∀ d, Anc t d v → d ∈ trace := by
  simp only [treeOk, Bool.and_eq_true, List.all_eq_true] at ok
  obtain ⟨rooted, edges⟩ := ok
  induction walk with
  | @start e entry =>
      refine ⟨by simp [inTree, entry], ?_⟩
      intro d above
      cases above with
      | refl => simp
      | up parent _ =>
          rw [entry] at rooted
          simp [parent] at rooted
  | @step u v trace _ edge before =>
      obtain ⟨held, dominated⟩ := before
      obtain ⟨b, member, labelled, successor⟩ := edge
      have fits := edges b member
      rw [labelled, held] at fits
      simp only [Bool.not_true, Bool.false_or, List.all_eq_true] at fits
      have toV := fits v successor
      split at toV
      · rename_i p parent
        have pu : Anc t p u := isAnc_sound t p _ _ toV
        refine ⟨by simp [inTree, parent], ?_⟩
        intro d above
        cases above with
        | refl => simp
        | up parent' dp =>
            rw [parent] at parent'
            cases parent'
            exact List.mem_append_left _ (dominated d (anc_trans dp pu))
      · contradiction

/-- An instruction with an exception edge: its results are first seen in its normal successor. -/
def isInvoke (table : Table) (i : Ins) : Bool :=
  match table[i.op]? with
  | some spec => spec.labels == .invoke && i.labels.length == 2
  | none => false

/-- Each block by its label. -/
def blockMap (f : Fn) : Std.HashMap Nat Block := f.blocks.foldl (fun m b => m.insert b.label b) ∅

theorem blockMap_sound (f : Fn) : ∀ l b, (blockMap f)[l]? = some b → b ∈ f.blocks ∧ b.label = l := by
  suffices fold : ∀ (bs seen : List Block) (m : Std.HashMap Nat Block),
      (∀ l b, m[l]? = some b → b ∈ seen ∧ b.label = l) →
      ∀ l b, (bs.foldl (fun m b => m.insert b.label b) m)[l]? = some b → b ∈ seen ++ bs ∧ b.label = l by
    intro l b found
    have := fold f.blocks [] ∅ (by intro l b none; simp at none) l b found
    simpa using this
  intro bs
  induction bs with
  | nil => intro seen m held l b found; simpa using held l b found
  | cons c rest step =>
      intro seen m held l b found
      have := step (seen ++ [c]) (m.insert c.label c) (by
        intro l b found
        rw [Std.HashMap.getElem?_insert] at found
        split at found
        · rename_i same
          cases found
          exact ⟨by simp, by simpa using same⟩
        · obtain ⟨member, labelled⟩ := held l b found
          exact ⟨by simp [member], labelled⟩) l b found
      simpa using this

/-- Where each value number is defined: its block's label and the instruction's index there.
Its entries are only claims: `lookup` checks each against the blocks. -/
def defMap (f : Fn) : Std.HashMap Nat (Nat × Nat) :=
  f.blocks.foldl (fun m b => b.code.zipIdx.foldl
    (fun m entry => entry.1.results.foldl (fun m x => m.insert x (b.label, entry.2)) m) m) ∅

/-- The definition of `x` that `dm` claims, where its block holds it there. -/
def lookup (bm : Std.HashMap Nat Block) (dm : Std.HashMap Nat (Nat × Nat)) (x : Nat) :
    Option (Block × Nat × Ins) :=
  match dm[x]? with
  | none => none
  | some (a, k) =>
    match bm[a]? with
    | none => none
    | some db =>
      match db.code[k]? with
      | none => none
      | some d => if d.results.contains x then some (db, k, d) else none

theorem lookup_sound (f : Fn) (dm : Std.HashMap Nat (Nat × Nat)) {x k : Nat} {db : Block} {d : Ins}
    (found : lookup (blockMap f) dm x = some (db, k, d)) :
    db ∈ f.blocks ∧ db.code[k]? = some d ∧ x ∈ d.results := by
  unfold lookup at found
  split at found
  · contradiction
  · split at found
    · contradiction
    · rename_i db' inMap
      split at found
      · contradiction
      · rename_i d' at_k
        split at found
        · rename_i has
          simp only [Option.some.injEq, Prod.mk.injEq] at found
          obtain ⟨rfl, rfl, rfl⟩ := found
          exact ⟨(blockMap_sound f _ _ inMap).1, at_k, List.contains_iff_mem.mp has⟩
        · contradiction

/-- Every block with `n` among its successors is the block labelled `a`. -/
def onlyFrom (f : Fn) (n a : Nat) : Bool :=
  f.blocks.all fun b => !(successors b).contains n || b.label == a

theorem onlyFrom_sound {f : Fn} {n a : Nat} (only : onlyFrom f n a = true) :
    ∀ c ∈ f.blocks, n ∈ successors c → c.label = a := by
  intro c member successor
  simp only [onlyFrom, List.all_eq_true] at only
  have held := only c member
  rw [List.contains_iff_mem.mpr successor] at held
  simpa using held

/-- Whether `x` is defined before instruction `j` of block `u`. -/
def definedBefore (table : Table) (f : Fn) (t : Tree) (bm : Std.HashMap Nat Block)
    (dm : Std.HashMap Nat (Nat × Nat)) (x u j : Nat) : Bool :=
  match lookup bm dm x with
  | none => false
  | some (db, k, d) =>
    if isInvoke table d then
      match d.labels.head? with
      | none => false
      | some n => onlyFrom f n db.label && (n == u || (n != u && isProper f t n u))
    else (db.label == u && decide (k < j)) || (db.label != u && isProper f t db.label u)

/-- Whether `x` is defined before the end of block `p`, where a phi reads it from `p`. -/
def definedAtEnd (table : Table) (f : Fn) (t : Tree) (bm : Std.HashMap Nat Block)
    (dm : Std.HashMap Nat (Nat × Nat)) (x p : Nat) : Bool :=
  match lookup bm dm x with
  | none => false
  | some (db, _, d) =>
    if isInvoke table d then
      match d.labels.head? with
      | none => false
      | some n => onlyFrom f n db.label && isAnc t n (fuel f) p
    else isAnc t db.label (fuel f) p

/-- Every value that an instruction of a block of the tree reads is defined before the read. -/
def checkUses (table : Table) (f : Fn) (t : Tree) : Bool :=
  let bm := blockMap f
  let dm := defMap f
  f.blocks.all fun b => !inTree f t b.label || b.code.zipIdx.all fun entry =>
    if entry.1.joins then
      (entry.1.operands.zip entry.1.labels).all fun read =>
        read.1.kind != 0 || !inTree f t read.2 || definedAtEnd table f t bm dm read.1.number read.2
    else
      entry.1.operands.all fun a => a.kind != 0 || definedBefore table f t bm dm a.number b.label entry.2

def checkDominance (table : Table) (f : Fn) (t : Tree) : Bool := treeOk f t && checkUses table f t

/-- How a definition at instruction `k` of block `db` reaches a read at instruction `j` of block
`u` along `trace`, a path from the entry block to `u`: earlier in `u`, or in a block the path
went through before `u`. An invoke's results are first seen at the start of its normal
successor `n`, whose only predecessor is the invoke's block. -/
def SeenBefore (table : Table) (f : Fn) (db : Block) (k : Nat) (d : Ins) (u j : Nat)
    (trace : List Nat) : Prop :=
  if isInvoke table d = true then
    ∃ n, d.labels.head? = some n ∧ (∀ c ∈ f.blocks, n ∈ successors c → c.label = db.label) ∧
      (n = u ∨ (n ≠ u ∧ n ∈ trace))
  else (db.label = u ∧ k < j) ∨ (db.label ≠ u ∧ db.label ∈ trace)

/-- How a definition in block `db` reaches the end of a path from the entry block (a phi's
predecessor): through a block of the path. -/
def SeenAtEnd (table : Table) (f : Fn) (db : Block) (d : Ins) (trace : List Nat) : Prop :=
  if isInvoke table d = true then
    ∃ n, d.labels.head? = some n ∧ (∀ c ∈ f.blocks, n ∈ successors c → c.label = db.label) ∧
      n ∈ trace
  else db.label ∈ trace

theorem definedBefore_sound (table : Table) (f : Fn) (t : Tree) (ok : treeOk f t = true)
    (dm : Std.HashMap Nat (Nat × Nat)) {x u j : Nat}
    (found : definedBefore table f t (blockMap f) dm x u j = true) {trace : List Nat}
    (walk : Walk f u trace) :
    ∃ db ∈ f.blocks, ∃ (k : Nat) (d : Ins), db.code[k]? = some d ∧ x ∈ d.results ∧ SeenBefore table f db k d u j trace := by
  have dominated := (walk_dominated f t ok walk).2
  unfold definedBefore at found
  split at found
  · contradiction
  · rename_i db k d looked
    obtain ⟨member, at_k, has⟩ := lookup_sound f dm looked
    refine ⟨db, member, k, d, at_k, has, ?_⟩
    unfold SeenBefore
    split
    · rename_i invoke
      simp only [invoke, ite_true] at found
      split at found
      · contradiction
      · rename_i n head
        simp only [Bool.and_eq_true, Bool.or_eq_true, beq_iff_eq, bne_iff_ne, ne_eq] at found
        obtain ⟨only, reach⟩ := found
        refine ⟨n, head, onlyFrom_sound only, ?_⟩
        rcases reach with same | ⟨other, proper⟩
        · exact Or.inl same
        · exact Or.inr ⟨other, dominated n (proper_anc proper)⟩
    · rename_i invoke
      simp only [invoke, Bool.false_eq_true, ite_false, Bool.or_eq_true, Bool.and_eq_true, beq_iff_eq,
        decide_eq_true_eq, bne_iff_ne, ne_eq] at found
      rcases found with ⟨same, before⟩ | ⟨other, proper⟩
      · exact Or.inl ⟨same, before⟩
      · exact Or.inr ⟨other, dominated db.label (proper_anc proper)⟩

theorem definedAtEnd_sound (table : Table) (f : Fn) (t : Tree) (ok : treeOk f t = true)
    (dm : Std.HashMap Nat (Nat × Nat)) {x p : Nat}
    (found : definedAtEnd table f t (blockMap f) dm x p = true) {trace : List Nat}
    (walk : Walk f p trace) :
    ∃ db ∈ f.blocks, ∃ (k : Nat) (d : Ins), db.code[k]? = some d ∧ x ∈ d.results ∧ SeenAtEnd table f db d trace := by
  have dominated := (walk_dominated f t ok walk).2
  unfold definedAtEnd at found
  split at found
  · contradiction
  · rename_i db k d looked
    obtain ⟨member, at_k, has⟩ := lookup_sound f dm looked
    refine ⟨db, member, k, d, at_k, has, ?_⟩
    unfold SeenAtEnd
    split
    · rename_i invoke
      simp only [invoke, ite_true] at found
      split at found
      · contradiction
      · rename_i n head
        simp only [Bool.and_eq_true] at found
        obtain ⟨only, reach⟩ := found
        exact ⟨n, head, onlyFrom_sound only, dominated n (isAnc_sound t n _ _ reach)⟩
    · rename_i invoke
      simp only [invoke, Bool.false_eq_true, ite_false] at found
      exact dominated db.label (isAnc_sound t _ _ _ found)

/-- In an accepted function, on every path from the entry block to an instruction that is no
phi, each value it reads is defined earlier in the instruction's block, or in a block the path
went through before. -/
theorem accepted_defined_before_use (table : Table) (f : Fn) (t : Tree)
    (accepted : checkDominance table f t = true)
    {b : Block} (member : b ∈ f.blocks) {i : Ins} {j : Nat} (at_j : b.code[j]? = some i)
    (plain : i.joins = false) {a : Operand} (read : a ∈ i.operands) (value : a.kind = 0)
    {trace : List Nat} (walk : Walk f b.label trace) :
    ∃ db ∈ f.blocks, ∃ (k : Nat) (d : Ins), db.code[k]? = some d ∧ a.number ∈ d.results ∧
      SeenBefore table f db k d b.label j trace := by
  simp only [checkDominance, Bool.and_eq_true] at accepted
  obtain ⟨ok, uses⟩ := accepted
  have held := (walk_dominated f t ok walk).1
  simp only [checkUses, List.all_eq_true] at uses
  have block := uses b member
  simp only [held, Bool.not_true, Bool.false_or, List.all_eq_true] at block
  have entry := block (i, j) (List.mem_zipIdx_iff_getElem?.mpr at_j)
  simp only [plain, Bool.false_eq_true, ite_false, List.all_eq_true] at entry
  have found := entry a read
  simp only [Bool.or_eq_true, bne_iff_ne, ne_eq, value, not_true_eq_false, false_or] at found
  exact definedBefore_sound table f t ok _ found walk

/-- In an accepted function, each value that a phi of a block on some path reads from a
predecessor is defined on every path from the entry block to the end of that predecessor. -/
theorem accepted_phi_defined (table : Table) (f : Fn) (t : Tree)
    (accepted : checkDominance table f t = true)
    {b : Block} (member : b ∈ f.blocks) {i : Ins} {j : Nat} (at_j : b.code[j]? = some i)
    (phi : i.joins = true) {a : Operand} {p : Nat} (read : (a, p) ∈ i.operands.zip i.labels)
    (value : a.kind = 0) {path : List Nat} (reached : Walk f b.label path)
    {trace : List Nat} (walk : Walk f p trace) :
    ∃ db ∈ f.blocks, ∃ (k : Nat) (d : Ins), db.code[k]? = some d ∧ a.number ∈ d.results ∧
      SeenAtEnd table f db d trace := by
  simp only [checkDominance, Bool.and_eq_true] at accepted
  obtain ⟨ok, uses⟩ := accepted
  have held := (walk_dominated f t ok reached).1
  have from_p := (walk_dominated f t ok walk).1
  simp only [checkUses, List.all_eq_true] at uses
  have block := uses b member
  simp only [held, Bool.not_true, Bool.false_or, List.all_eq_true] at block
  have entry := block (i, j) (List.mem_zipIdx_iff_getElem?.mpr at_j)
  simp only [phi, ite_true, List.all_eq_true] at entry
  have found := entry (a, p) read
  simp only [Bool.or_eq_true, bne_iff_ne, ne_eq, value, not_true_eq_false, false_or, from_p,
    Bool.not_true, Bool.false_eq_true] at found
  exact definedAtEnd_sound table f t ok _ found walk

end PystachyDominance
