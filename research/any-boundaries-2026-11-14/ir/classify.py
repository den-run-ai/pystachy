"""Join the complete raw ledger, explicit input overlay and per-case IR reviews."""
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
original = json.loads((ROOT / "summary.json").read_text())
identity = json.loads((ROOT / "new-identity.json").read_text())
final = json.loads((ROOT / "final-summary.json").read_text()) if (ROOT / "final-summary.json").exists() else original
if "final_source" not in final:
    final.update(final_source=identity["source_ref"], final_published=identity["evidence"]["published_ref"], final_tree=identity["source_tree"])
if (ROOT / "final-tree.json").exists():
    final_tree = json.loads((ROOT / "final-tree.json").read_text())
    final.update({key: final_tree[key] for key in ("final_source", "final_published", "final_tree")})
inventory = json.loads((ROOT / "inventory.json").read_text())
added = set(inventory["added_paths"])
reviews = json.loads((ROOT / "constructor-semantic-review.json").read_text()) + json.loads((ROOT / "numeric-semantic-review.json").read_text())
by_number = {row["number"]: row for row in reviews}
assert len(by_number) == len(reviews) == original["counts"]["ir_change"]
assert set(by_number) == {row["number"] for row in original["cases"] if row["category"] == "ir_change"}
assert not any(row["unexpected"] for row in reviews), "Unresolved IR finding"

acceptances = {
    129: "Imported constructor dependency resolved through an imported alias while retaining fixed field layout.",
    130: "Demanded imported child/base constructor dependency becomes nominal without eagerly preparing unrelated siblings.",
    131: "Imported constructor dependency resolved through a module-qualified class name.",
    132: "Imported constructor dependency resolved through a quoted forward annotation.",
    133: "Fixed-layout child constructor specializes the variable-layout input class instead of forcing that input to a single nominal layout.",
    134: "Demanded imported hierarchy follows transitive constructor dependencies before fixing the child layout.",
    137: "Generic constructor on a fixed-field base now specializes constructor code while retaining one inheritable layout.",
    138: "Generic constructor on a fixed-field leaf retains its nominal inheritance hierarchy.",
    139: "Fixed-field generic constructors support inheritance without introducing Any storage.",
    150: "Imported fixed-layout hierarchy can be constructed and boxed through Any using its nominal class identity.",
    151: "Class checks can demand a deferred imported fixed-layout hierarchy before the constructor call.",
    152: "Constructor parameter dependencies within an imported fixed-layout hierarchy are prepared on demand.",
    153: "Direct iterable-taking generic constructors retain fixed layouts throughout inheritance.",
    154: "Imported direct generic constructors participate in fixed-layout inheritance and specialized caller code.",
    155: "Recursive fixed-layout hierarchy is discovered and prepared on demand.",
    156: "Recursive fixed-layout child supports constructor specialization with one nominal layout.",
    157: "Imported recursive fixed-layout child is prepared without forcing unrelated imported declarations.",
    158: "Quoted recursive hierarchy annotations retain fixed nominal layouts.",
    668: "isinstance of boxed generic specializations uses their common Python class origin without selecting a payload layout.",
    669: "type(value) is GenericClass works across non-opt-in imported helper boundaries.",
    670: "Generic class identity checks remain consistent when imported call/declaration discovery order changes.",
}
diagnostics = {
    2762: "The fixed-layout hierarchy is now admissible, so the compiler reaches the existing unsupported Annotated parameter annotation and reports that specific error. Status remains 1; no unsupported annotation is accepted.",
    2764: "Demanded hierarchy analysis distinguishes its concrete annotated dependency from the remaining variable-layout constructor; the rejection changes from the iterator-template explanation to the requirement for concrete constructor parameters. Status remains 1.",
    2765: "The live fixed-layout hierarchy now reaches its invalid override body and reports the missing attribute at the defining module, with the original caller context. Unused invalid siblings remain lazy; the requested invalid method still rejects with status 1.",
}

counts = Counter()
changes = []
final_by_number = {row["number"]: row for row in final["cases"]}
for row in original["cases"]:
    if row["category"] == "identical":
        continue
    number, category = row["number"], row["category"]
    result = {key: row[key] for key in ("number", "case", "category", "old_status", "new_status", "source_sha256", "directory")}
    result["new_fixture"] = row["case"] in added
    if category == "ir_change":
        result["review"] = by_number[number]
        result["rationale"] = by_number[number]["rationale"]
        result["causes"] = by_number[number]["causes"]
    elif category == "new_acceptance":
        result["rationale"] = acceptances[number]
        result["causes"] = ["generic_class_identity"] if number >= 668 else ["fixed_layout_constructor_acceptance"]
        result["old_diagnostic"] = (ROOT / row["directory"] / "old.msg").read_text()
        assert result["new_fixture"]
    elif category == "diagnostic_change":
        result["rationale"] = diagnostics[number]
        result["causes"] = ["later_specific_rejection"]
        result["old_diagnostic"] = row["old_diagnostic"]
        result["new_diagnostic"] = row["new_diagnostic"]
        assert result["new_fixture"]
    elif category == "generated_home_only":
        result["rationale"] = "Only the exact equal-length compiler-private home prefix differs, in recognized generated ImportError location constants or compiler-home/sys.prefix constants. Every raw byte remains retained; arbitrary literals are not normalized."
        result["causes"] = ["generated_home_location"]
    elif category == "diagnostic_home_only":
        result["rationale"] = "The repository oracle conservatively left diagnostics containing apostrophes raw. The complete messages differ only in the exact private-home source-location shapes recognized by inspect.py; wording, line numbers, call context and status are unchanged."
        result["causes"] = ["diagnostic_home_location"]
    else:
        raise AssertionError((number, category))
    finalrow = final_by_number[number]
    result["final_category"] = finalrow["category"]
    if finalrow.get("overlay"):
        result["final_source_sha256"] = finalrow["source_sha256"]
        result["final_rationale"] = "The final recording correction removed the resolved optional-list observation; the remaining deviation input compiles byte-identically under both compilers. See overlay/manifest.json. The original substantive difference remains retained here."
    else:
        for cause in result["causes"]:
            counts[cause] += 1
    changes.append(result)
assert len(changes) == original["total"] - original["counts"]["identical"]
assert set(acceptances) == {row["number"] for row in original["cases"] if row["category"] == "new_acceptance"}
assert set(diagnostics) == {row["number"] for row in original["cases"] if row["category"] == "diagnostic_change"}
status_changes = [row for row in final["cases"] if row["old_status"] != row["new_status"]]
assert len(status_changes) == 21
assert all(row["old_status"] == 1 and row["new_status"] == 0 for row in status_changes)

effect_fixed = '"vtuple.box": "%ptr:%ptr|R A rO wO|"' in (ROOT / "home-new/src/pystachy_compiler/specs.py").read_text()
out = {"baseline_source": json.loads((ROOT / "old-identity.json").read_text())["source_ref"],
       "full_audit_source": json.loads((ROOT / "new-identity.json").read_text())["source_ref"],
       "final_source": final["final_source"], "final_published": final["final_published"], "final_tree": final["final_tree"],
       "total": final["total"], "full_audit_counts": original["counts"], "final_counts": final["counts"],
       "corpus_inventory": inventory, "final_raw_differences": final["total"] - final["counts"]["identical"],
       "qualification_status": "IR classification complete after vtuple.box effect correction" if effect_fixed else "Superseded preceding-head audit: missing vtuple.box write effects require a fresh bootstrap and full audit",
       "vtuple_box_effect_contract_fixed": effect_fixed,
       "review_findings": json.loads((ROOT / "numeric-review-qualification.json").read_text())["findings"] if (ROOT / "numeric-review-qualification.json").exists() else [],
       "new_rejections": [], "other_status_changes": [], "unresolved_differences": [],
       "final_cause_counts_nonexclusive": dict(sorted(counts.items())),
       "existing_case_counts": dict(Counter(row["category"] for row in final["cases"] if row["case"] not in added)),
       "added_case_counts": dict(Counter(row["category"] for row in final["cases"] if row["case"] in added)),
       "changes": changes}
(ROOT / "classification.json").write_text(json.dumps(out, indent=2) + "\n")
(ROOT / "final-ledger.jsonl").write_text("".join(json.dumps(row) + "\n" for row in final["cases"]))

lines = ["# Complete IR difference classification", "",
         f"The final ledger covers every one of the {final['total']:,} corpus inputs. All {len(changes)} original differences below remain retained. Any final-input overlay is recorded separately.", "",
         out["qualification_status"] + ".", "",
         "## Outcome", "", "| Final classification | Cases |", "|---|---:|"]
for category, number in final["counts"].items():
    lines.append(f"| {category} | {number} |")
lines += ["", "There are zero new rejections, zero other status changes and zero unresolved differences. All 21 new acceptances and all three changed rejection diagnostics are newly added fixtures. Existing rejection diagnostics change only by private-home locations.", "",
          "## Every original difference", "", "| Number | Case | Original → final category | Explanation |", "|---:|---|---|---|"]
for row in changes:
    reason = row["rationale"] + (" " + row["final_rationale"] if "final_rationale" in row else "")
    lines.append(f"| {row['number']} | `{row['case']}` | {row['category']} → {row['final_category']} | {reason.replace('|', '&#124;')} |")
lines += ["", "## Changed rejection diagnostics", ""]
for row in changes:
    if row["category"] != "diagnostic_change":
        continue
    lines += ["### " + row["case"], "", row["rationale"], "", "Old:", "", "```text", row["old_diagnostic"].rstrip(), "```", "", "New:", "", "```text", row["new_diagnostic"].rstrip(), "```", ""]
(ROOT / "classification.md").write_text("\n".join(lines) + "\n")
print(json.dumps({key: out[key] for key in ("total", "final_counts", "final_raw_differences", "existing_case_counts", "added_case_counts", "final_cause_counts_nonexclusive")}, indent=2))
