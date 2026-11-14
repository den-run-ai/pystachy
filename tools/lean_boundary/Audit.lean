-- SPDX-License-Identifier: MIT
import Lean
import PystachyBoundary
import PystachyLayout
import PystachyAlias
import PystachyCompanion
import PystachyAccess
import PystachyInt
import PystachyInline
import PystachyStorage

/- Fail the build if the public guarantees depend on an admitted proof, a
custom assumption, or native computation trusted by the kernel. The three
allowed axioms are Lean's standard logical axioms, not assumptions about IR. -/
open Lean in
run_cmd do
  let allowed := #[``propext, ``Classical.choice, ``Quot.sound]
  for theoremName in #[``PystachyBoundary.check_iff,
      ``PystachyLayout.checked_projection, ``PystachyLayout.accepted_layout_projection,
      ``PystachyAlias.accepted_reference_roundtrip, ``PystachyAlias.accepted_alias_write,
      ``PystachyAlias.accepted_traces_reference, ``PystachyAlias.accepted_root_chain,
      ``PystachyCompanion.accepted_identity_roundtrip,
      ``PystachyCompanion.accepted_traces_identity,
      ``PystachyCompanion.accepted_root_chain, ``PystachyCompanion.accepted_boxed_root_chain,
      ``PystachyBoundary.reachable_facts, ``PystachyBoundary.accepted_payload_safe,
      ``PystachyAccess.reachable_invariant, ``PystachyAccess.accepted_access_safe,
      ``PystachyAccess.writeField_step, ``PystachyAccess.accepted_write_progress,
      ``PystachyInt.known_fits, ``PystachyInt.mod_fits, ``PystachyInt.floordiv_fits,
      ``PystachyInt.shr_fits, ``PystachyInt.shl_exact, ``PystachyInt.bitwise_fits,
      ``PystachyInt.and_mask,
      ``PystachyInline.no_overflow_exact, ``PystachyInline.no_overflow_fits,
      ``PystachyInline.accepted_arithmetic_exact,
      ``PystachyStorage.low_of_fit, ``PystachyStorage.promoting_decode,
      ``PystachyStorage.plain_view_safe, ``PystachyStorage.plain_marker_has_no_tail,
      ``PystachyStorage.null_digits_narrow, ``PystachyStorage.slot_fits_iff,
      ``PystachyStorage.pair_truth_zero, ``PystachyStorage.layout_has_tail,
      ``PystachyStorage.accepted_low_word, ``PystachyStorage.accepted_plain_view,
      ``PystachyStorage.accepted_tail_read, ``PystachyStorage.accepted_narrowing,
      ``PystachyStorage.accepted_slot_narrowing,
      ``PystachyStorage.accepted_optional_slot_narrowing,
      ``PystachyStorage.accepted_stack_copy,
      ``PystachyStorage.erase_read_move_iff, ``PystachyStorage.projected_reachable,
      ``PystachyStorage.accepted_projected_payload] do
    let axioms ← collectAxioms theoremName
    for axiomName in axioms do
      unless allowed.contains axiomName do
        throwError "{theoremName} depends on unapproved axiom {axiomName}"
    logInfo m!"{theoremName}: axiom audit passed ({axioms})"

#print axioms PystachyBoundary.accepted_payload_safe
#print axioms PystachyAccess.accepted_access_safe
#print axioms PystachyInt.known_fits
