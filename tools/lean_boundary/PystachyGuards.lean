-- SPDX-License-Identifier: MIT
import PystachyBoundary

/-! Nullness and closed-union obligations use the audited finite-tag semantics.
The bridge maps null to `null`, nonnull pointers to `nonnull`, and union members
to `member:<representation>`. These statements concern the normalized graph;
they deliberately make no assertion about exporter or runtime fidelity. -/
namespace PystachyGuards
open PystachyBoundary

theorem removed_check_nonnull {program : Program} {certificate : Certificate}
    {initial : Tags} {state : State} {value : Location} {next : Nat}
    (checked : check program certificate = true)
    (reachable : Reachable program initial state)
    (obligation : program.nodes[state.pc]? = some (.payload value ["nonnull"] next)) :
    state.tags value ≠ "null" := by
  have h := accepted_payload_safe checked reachable obligation
  simp only [List.mem_singleton] at h
  simp [h]

theorem union_member_matches {program : Program} {certificate : Certificate}
    {initial : Tags} {state : State} {value : Location} {member : String} {next : Nat}
    (checked : check program certificate = true)
    (reachable : Reachable program initial state)
    (obligation : program.nodes[state.pc]? = some (.payload value [member] next)) :
    state.tags value = member := by
  simpa only [List.mem_singleton] using accepted_payload_safe checked reachable obligation

theorem union_read_nonnull {program : Program} {certificate : Certificate}
    {initial : Tags} {state : State} {value : Location} {members : TagSet} {next : Nat}
    (checked : check program certificate = true)
    (reachable : Reachable program initial state)
    (obligation : program.nodes[state.pc]? = some (.payload value members next))
    (excludesNull : "null" ∉ members) : state.tags value ≠ "null" := by
  intro isNull
  exact excludesNull (isNull ▸ accepted_payload_safe checked reachable obligation)

def nullableJoin : Program := ⟨[
  .guard "x" ["null", "nonnull"] 1 5,
  .guard "x" ["null"] 2 3,
  .jump 4, .jump 4,
  .payload "x" ["nonnull"] 5, .stop], 0⟩
example : check nullableJoin [[], [("x", ["null", "nonnull"])],
    [("x", ["null"])], [("x", ["nonnull"])], [("x", ["null", "nonnull"])], []] = false := by decide

def rebound : Program := ⟨[
  .guard "x" ["nonnull"] 1 3,
  .havoc "x" 2, .payload "x" ["nonnull"] 3, .stop], 0⟩
example : check rebound [[], [("x", ["nonnull"])], [("x", ["nonnull"])], []] = false := by decide

/-! Field initialization (`check_lean_fields.py`) maps each field of an object under
construction to a location whose tag is `set` once a store assigned it and `unset` before,
and each value that may be that object to a location whose tag names it (`obj:<object>`). An
unflagged read, an escape, a call's pre-condition or a return's post-condition requires `set`. -/
theorem field_assigned {program : Program} {certificate : Certificate}
    {initial : Tags} {state : State} {field : Location} {next : Nat}
    (checked : check program certificate = true)
    (reachable : Reachable program initial state)
    (obligation : program.nodes[state.pc]? = some (.payload field ["set"] next)) :
    state.tags field = "set" := by
  simpa only [List.mem_singleton] using accepted_payload_safe checked reachable obligation

/-- Constants `#set` and `#unset` hold their tags; the object's field starts unset, a store
assigns it, and the object escapes. -/
def storedThenEscaped : Program := ⟨[
  .guard "#set" ["set"] 1 7, .guard "#unset" ["unset"] 2 7,
  .copy "f" "#unset" 3, .copy "f" "#set" 4,
  .payload "f" ["set"] 5, .jump 6, .stop, .stop], 0⟩
example : check storedThenEscaped [[], [("#set", ["set"])],
    [("#set", ["set"]), ("#unset", ["unset"])], [("#set", ["set"])],
    [("f", ["set"])], [], [], []] = true := by decide

/-- The object escapes before the store. -/
def escapedFirst : Program := ⟨[
  .guard "#set" ["set"] 1 7, .guard "#unset" ["unset"] 2 7,
  .copy "f" "#unset" 3, .payload "f" ["set"] 4,
  .copy "f" "#set" 5, .jump 6, .stop, .stop], 0⟩
example : check escapedFirst [[], [("#set", ["set"])],
    [("#set", ["set"]), ("#unset", ["unset"])], [("f", ["unset"]), ("#set", ["set"])],
    [("#set", ["set"])], [], [], []] = false := by decide

/-- A store on one branch only: the join keeps both states, so the escape is rejected. -/
def storedOnOneBranch : Program := ⟨[
  .guard "#set" ["set"] 1 8, .guard "#unset" ["unset"] 2 8,
  .copy "f" "#unset" 3, .choice 4 5,
  .copy "f" "#set" 5, .payload "f" ["set"] 6, .stop, .stop, .stop], 0⟩
example : check storedOnOneBranch [[], [("#set", ["set"])],
    [("#set", ["set"]), ("#unset", ["unset"])], [("f", ["unset"]), ("#set", ["set"])],
    [("#set", ["set"])], [("f", ["set", "unset"])], [], [], []] = false := by decide
end PystachyGuards
