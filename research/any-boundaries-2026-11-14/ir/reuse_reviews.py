"""Transfer only reviews whose complete old/new records matched exactly."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PREVIOUS = ROOT.with_name("final-ir-audit")
comparison = json.loads((ROOT / "comparison-previous.json").read_text())
assert not comparison["requires_review"], comparison["requires_review"]
verified = {row["number"]: row for row in comparison["cases"] if row["reusable_review"]}
old = json.loads((PREVIOUS / "numeric-review-qualification.json").read_text())
old_cases = {row["number"]: row for row in old["cases"]}
rows = []
for new in json.loads((ROOT / "numeric-review-cases.json").read_text()):
    number = new["number"]
    assert number in verified and number in old_cases
    row = copy.deepcopy(old_cases[number])
    assert row["case"] == new["case"]
    row["previous_diff_sha256"] = row["diff_sha256"]
    diff = ROOT / new["directory"] / "ir.location-normalized.diff"
    row["diff"] = str(diff)
    row["diff_sha256"] = hashlib.sha256(diff.read_bytes()).hexdigest()
    row["review_reuse"] = {"previous_source": old["source"], "both_sides_exactly_compared": True,
                            "case_source_sha256_unchanged": True, "comparison": "comparison-previous.json",
                            "compared_ir_hashes": {side: verified[number]["sides"][side]["compared_ir_hashes"] for side in ("old", "new")}}
    rows.append(row)
result = copy.deepcopy(old)
identity = json.loads((ROOT / "new-identity.json").read_text())
result.update(source=identity["source_ref"], cases=rows, cases_reviewed=len(rows),
              status="Final native fixed-point source; every retained numeric review matched both complete IR records and diagnostics under exact generated-home replacement",
              exact_header_only=sum(row["exact_header_only"] for row in rows))
result["method"] += " Final review reuse additionally requires unchanged case source hashes and exact complete old/new IR/diagnostics after demonstrated equal-length generated-home replacements. No numeric instructions or types are normalized."
for finding in result["findings"]:
    finding["included_in_final_built_source"] = identity["source_ref"]
result["final_tools_correspondence"] = "final-tree.json"
(ROOT / "numeric-semantic-review.json").write_text(json.dumps(rows, indent=2) + "\n")
(ROOT / "numeric-review-qualification.json").write_text(json.dumps(result, indent=2) + "\n")
constructor_rows = json.loads((ROOT / "constructor-review-cases.json").read_text())
assert all(row["number"] in verified for row in constructor_rows)
print("Reused", len(rows), "numeric reviews; verified", len(constructor_rows), "constructor review inputs")
