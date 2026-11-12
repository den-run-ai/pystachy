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
end PystachyGuards
