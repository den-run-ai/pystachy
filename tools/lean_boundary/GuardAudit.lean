-- SPDX-License-Identifier: MIT
import Lean
import PystachyGuards

open Lean in
run_cmd do
  let allowed := #[``propext, ``Classical.choice, ``Quot.sound]
  for theoremName in #[``PystachyGuards.removed_check_nonnull,
      ``PystachyGuards.union_member_matches, ``PystachyGuards.union_read_nonnull,
      ``PystachyGuards.field_assigned] do
    let axioms ← collectAxioms theoremName
    for axiomName in axioms do
      unless allowed.contains axiomName do
        throwError "{theoremName} depends on unapproved axiom {axiomName}"
    logInfo m!"{theoremName}: axiom audit passed ({axioms})"
