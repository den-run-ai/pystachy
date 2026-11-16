-- SPDX-License-Identifier: MIT
import Std

/-! The six orchestration stages of `PipelineState`, numbered 1 through 6.
Zero means no completed/active stage. This model proves sequencing of recorded
transitions, not that a stage body establishes its semantic postcondition. -/
namespace PystachyPipeline

def stagePrefix (n : Nat) : List Nat := (List.range n).map (· + 1)

structure State where
  stage : Nat
  active : Nat
  history : List Nat
  deriving BEq, DecidableEq, Repr

/-- `decision` is `PipelineState.decide`: a typing, layout or specialization decision
(a template instance, a class specialization, a field layout). It changes no stage. -/
inductive Action where
  | begin (stage : Nat)
  | complete (stage : Nat)
  | decision
  deriving BEq, DecidableEq, Repr

def initial : State := ⟨0, 0, []⟩

def WellFormed (s : State) : Prop :=
  s.stage ≤ 6 ∧ s.history = stagePrefix s.stage ∧
    (s.active = 0 ∨ s.stage < 6 ∧ s.active = s.stage + 1)

instance (s : State) : Decidable (WellFormed s) := inferInstanceAs
  (Decidable (s.stage ≤ 6 ∧ s.history = stagePrefix s.stage ∧
    (s.active = 0 ∨ s.stage < 6 ∧ s.active = s.stage + 1)))

def step (s : State) : Action → Option State
  | .begin n =>
      if 1 ≤ n ∧ n ≤ 6 ∧ s.active = 0 ∧ s.stage + 1 = n then
        some { s with active := n }
      else none
  | .complete n =>
      if 1 ≤ n ∧ n ≤ 6 ∧ s.active = n ∧ s.stage + 1 = n then
        some ⟨n, 0, s.history ++ [n]⟩
      else none
  | .decision => if s.stage ≤ 1 then some s else none

theorem initial_wellFormed : WellFormed initial := by
  simp [WellFormed, initial, stagePrefix]

theorem step_preserves (s t : State) (action : Action)
    (valid : WellFormed s) (taken : step s action = some t) : WellFormed t := by
  rcases valid with ⟨bound, history, active⟩
  cases action with
  | begin n =>
      simp only [step] at taken
      split at taken
      · rename_i guard
        simp only [Option.some.injEq] at taken
        subst t
        rcases guard with ⟨_, limit, _, next⟩
        simp only [WellFormed]
        exact ⟨bound, history, Or.inr ⟨by omega, next.symm⟩⟩
      · contradiction
  | complete n =>
      simp only [step] at taken
      split at taken
      · rename_i guard
        simp only [Option.some.injEq] at taken
        subst t
        rcases guard with ⟨_, limit, _, next⟩
        refine ⟨limit, ?_, Or.inl rfl⟩
        rw [history, ← next]
        simp [stagePrefix, List.range_succ]
      · contradiction
  | decision =>
      simp only [step] at taken
      split at taken
      · simp only [Option.some.injEq] at taken
        subst t
        exact ⟨bound, history, active⟩
      · contradiction

inductive Reachable : State → Prop where
  | start : Reachable initial
  | next {s t : State} (action : Action) : Reachable s → step s action = some t → Reachable t

theorem reachable_wellFormed (s : State) (reachable : Reachable s) : WellFormed s := by
  induction reachable with
  | start => exact initial_wellFormed
  | next action _ taken previous => exact step_preserves _ _ action previous taken

theorem active_cannot_begin (s : State) (n : Nat) (active : s.active ≠ 0) :
    step s (.begin n) = none := by
  simp [step, active]

theorem consumed_cannot_step (s : State) (valid : WellFormed s)
    (consumed : s.stage = 6) (action : Action) : step s action = none := by
  have idle : s.active = 0 := by
    rcases valid.2.2 with idle | ⟨bound, _⟩
    · exact idle
    · omega
  cases action <;> simp [step, consumed, idle] <;> omega

theorem consumed_has_finalization (s : State) (valid : WellFormed s)
    (consumed : s.stage = 6) : 5 ∈ s.history := by
  rw [valid.2.1, consumed]
  decide

/-! Decisions belong to preparation and discovery. Analysis, optimization,
finalization and lowering consume a fixed set: none of them may add one. -/
theorem discovery_may_decide (s : State) (valid : WellFormed s)
    (discovering : s.active = 2) : step s .decision = some s := by
  have stage : s.stage = 1 := by
    rcases valid.2.2 with idle | ⟨_, next⟩ <;> omega
  simp [step, stage]

theorem consumers_cannot_decide (s : State) (valid : WellFormed s)
    (consuming : 3 ≤ s.active) : step s .decision = none := by
  have stage : 2 ≤ s.stage := by
    rcases valid.2.2 with idle | ⟨_, next⟩ <;> omega
  simp only [step]
  split
  · omega
  · rfl

theorem discovered_cannot_decide (s : State) (valid : WellFormed s)
    (discovered : 2 ∈ s.history) : step s .decision = none := by
  rw [valid.2.1] at discovered
  simp only [stagePrefix, List.mem_map, List.mem_range] at discovered
  obtain ⟨i, below, two⟩ := discovered
  simp only [step]
  split
  · omega
  · rfl

/-! Actual report normalization. Status is 0 failed, 1 retry, 2 completed;
evidence is 0 unavailable, 1 partial, 2 completed. The bridge supplies these
values directly from the report; Lean checks their consistency. -/
structure Attempt where
  index : Nat
  status : Nat
  consistent : Bool
  complete : Bool
  state : State
  evidence : List Nat
  deriving Repr

def evidence (a : Attempt) : List Nat := (stagePrefix 6).map fun n =>
  if n ≤ a.state.stage then (if a.complete then 2 else 1)
  else if n = a.state.active then 1 else 0

def checkAttempt (a : Attempt) (index : Nat) (terminal : Bool) (target : Nat) : Bool :=
  decide (WellFormed a.state) && a.index == index && a.consistent &&
  a.evidence == evidence a &&
  if terminal then
    a.status == 2 && a.complete && a.state.stage == target && a.state.active == 0
  else a.status == 1 && !a.complete && a.state.stage < target && a.state.active != 0

structure Report where
  attempts : List Attempt
  reportComplete : Bool
  sourceConsistent : Bool
  snapshotComplete : Bool
  snapshotAttempt : Nat
  target : Nat
  deriving Repr

def checkReport (r : Report) : Bool :=
  r.reportComplete && r.sourceConsistent && r.snapshotComplete &&
  !r.attempts.isEmpty && r.snapshotAttempt == r.attempts.length &&
  (r.target == 5 || r.target == 6) &&
  (r.attempts.zipIdx).all fun (a, i) =>
    checkAttempt a (i + 1) (i + 1 == r.attempts.length) r.target

theorem accepted_report_complete (r : Report) (accepted : checkReport r = true) :
    r.reportComplete = true ∧ r.sourceConsistent = true ∧
    r.snapshotComplete = true ∧ r.snapshotAttempt = r.attempts.length := by
  simp only [checkReport, Bool.and_eq_true, beq_iff_eq] at accepted
  exact ⟨accepted.1.1.1.1.1.1, accepted.1.1.1.1.1.2,
    accepted.1.1.1.1.2, accepted.1.1.2⟩

theorem accepted_attempt_ordered (a : Attempt) (index : Nat) (terminal : Bool) (target : Nat)
    (accepted : checkAttempt a index terminal target = true) :
    WellFormed a.state ∧ a.index = index := by
  simp only [checkAttempt, Bool.and_eq_true, decide_eq_true_eq, beq_iff_eq] at accepted
  exact ⟨accepted.1.1.1.1, accepted.1.1.1.2⟩

theorem accepted_terminal_target (a : Attempt) (index target : Nat)
    (accepted : checkAttempt a index true target = true) :
    a.state.stage = target ∧ a.state.active = 0 := by
  simp only [checkAttempt, Bool.and_eq_true, decide_eq_true_eq, beq_iff_eq,
    ↓reduceIte] at accepted
  exact ⟨accepted.2.1.2, accepted.2.2⟩

theorem accepted_report_target (r : Report) (accepted : checkReport r = true) :
    r.target = 5 ∨ r.target = 6 := by
  simp only [checkReport, Bool.and_eq_true, Bool.or_eq_true, beq_iff_eq] at accepted
  exact accepted.1.2

theorem accepted_terminal_consumed (a : Attempt) (index : Nat)
    (accepted : checkAttempt a index true 6 = true) :
    a.state.stage = 6 ∧ a.state.active = 0 ∧ 5 ∈ a.state.history := by
  have valid := (accepted_attempt_ordered a index true 6 accepted).1
  simp only [checkAttempt, Bool.and_eq_true, decide_eq_true_eq, beq_iff_eq,
    ↓reduceIte] at accepted
  exact ⟨accepted.2.1.2, accepted.2.2,
    consumed_has_finalization a.state valid accepted.2.1.2⟩

theorem accepted_report_attempts (r : Report) (accepted : checkReport r = true) :
    ∀ a i, (a, i) ∈ r.attempts.zipIdx →
      checkAttempt a (i + 1) (i + 1 == r.attempts.length) r.target = true := by
  simp only [checkReport, Bool.and_eq_true] at accepted
  intro a i member
  exact List.all_eq_true.mp accepted.2 (a, i) member

example : step initial (.complete 0) = none := by decide
example : step initial (.begin 2) = none := by decide
example : step ⟨5, 0, stagePrefix 5⟩ (.begin 6) = some ⟨5, 6, stagePrefix 5⟩ := by decide
example : step ⟨5, 6, stagePrefix 5⟩ (.begin 6) = none := by decide
example : step ⟨5, 6, stagePrefix 5⟩ (.complete 6) = some ⟨6, 0, stagePrefix 6⟩ := by decide
example : step ⟨1, 2, stagePrefix 1⟩ .decision = some ⟨1, 2, stagePrefix 1⟩ := by decide
example : step ⟨2, 0, stagePrefix 2⟩ .decision = none := by decide

end PystachyPipeline
