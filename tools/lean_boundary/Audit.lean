-- SPDX-License-Identifier: MIT
import Lean
import PystachyBoundary
import PystachyInt

/- Fail the build if the public guarantees depend on an admitted proof, a
custom assumption, or native computation trusted by the kernel. The three
allowed axioms are Lean's standard logical axioms, not assumptions about IR. -/
open Lean in
run_cmd do
  let allowed := #[``propext, ``Classical.choice, ``Quot.sound]
  for theoremName in #[``PystachyBoundary.check_iff,
      ``PystachyBoundary.reachable_facts, ``PystachyBoundary.accepted_payload_safe,
      ``PystachyInt.known_fits, ``PystachyInt.mod_fits, ``PystachyInt.floordiv_fits,
      ``PystachyInt.shr_fits, ``PystachyInt.shl_exact, ``PystachyInt.bitwise_fits,
      ``PystachyInt.and_mask] do
    let axioms ← collectAxioms theoremName
    for axiomName in axioms do
      unless allowed.contains axiomName do
        throwError "{theoremName} depends on unapproved axiom {axiomName}"
    logInfo m!"{theoremName}: axiom audit passed ({axioms})"

#print axioms PystachyBoundary.accepted_payload_safe
#print axioms PystachyInt.known_fits
