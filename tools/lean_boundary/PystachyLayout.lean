-- SPDX-License-Identifier: MIT
import PystachyBoundary

/-! Descriptor ancestry alone is not a layout proof. The adapter exports each
class's actual ordered representation/LLVM member pairs, including assignment
flags and identity companions. For every descriptor admitted by a payload read,
this checker requires the requested layout to be an exact prefix. The exporter,
LLVM's struct offsets and the runtime's pointer payload remain trusted. -/
namespace PystachyLayout
open PystachyBoundary

abbrev Layout := List String
structure Obligation where
  actual : Layout
  expected : Layout
  deriving Repr, DecidableEq

def Compatible (actual expected : Layout) : Prop :=
  expected.length ≤ actual.length ∧
  ∀ index ∈ List.range expected.length, actual[index]? = expected[index]?

instance (actual expected : Layout) : Decidable (Compatible actual expected) := by
  unfold Compatible
  infer_instance

def check (obligations : List Obligation) : Bool :=
  obligations.all (fun item => decide (Compatible item.actual item.expected))

theorem checked_projection {obligations : List Obligation} {item : Obligation}
    (checked : check obligations = true) (present : item ∈ obligations)
    {index : Nat} (inside : index < item.expected.length) :
    item.actual[index]? = item.expected[index]? := by
  have compatible : Compatible item.actual item.expected := by
    exact of_decide_eq_true ((List.all_eq_true.mp checked) item present)
  exact compatible.2 index (List.mem_range.mpr inside)

/-- Connect tag safety to a checked physical projection. The adapter must list
an obligation for every tag admitted by this read, not just its nominal class. -/
theorem accepted_layout_projection {program : Program} {certificate : Certificate}
    {initial : Tags} {state : State} {value : Location} {tags : TagSet} {next : Nat}
    {actual : Tag → Layout} {expected : Layout} {obligations : List Obligation}
    (guards : PystachyBoundary.check program certificate = true)
    (layouts : check obligations = true)
    (reached : Reachable program initial state)
    (read : program.nodes[state.pc]? = some (.payload value tags next))
    (inventory : ∀ tag ∈ tags, ⟨actual tag, expected⟩ ∈ obligations)
    {index : Nat} (inside : index < expected.length) :
    (actual (state.tags value))[index]? = expected[index]? := by
  have admitted := accepted_payload_safe guards reached read
  exact checked_projection layouts (inventory (state.tags value) admitted) inside

example : check [⟨["int:i64", "str:ptr", "bool:i1", "dyn:ptr"],
                    ["int:i64", "str:ptr", "bool:i1"]⟩] = true := by decide
-- Same LLVM pointer width cannot justify a changed source representation.
example : check [⟨["str:ptr"], ["list[int]:ptr"]⟩] = false := by decide
example : check [⟨["int:i64"], ["int:i64", "dyn:ptr"]⟩] = false := by decide
example : check [⟨["dyn:ptr", "bool:i1"], ["bool:i1", "dyn:ptr"]⟩] = false := by decide
end PystachyLayout
