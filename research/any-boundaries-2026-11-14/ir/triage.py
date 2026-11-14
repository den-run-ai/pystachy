"""Retain complete supplemental diffs and partition reviewed IR cases."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
summary = json.loads((ROOT / "summary.json").read_text())
rows = []
for case in summary["cases"]:
    if case["category"] != "ir_change":
        continue
    directory = ROOT / case["directory"]
    result = subprocess.run(["diff", "-u", "--label=old.location-normalized.ll", "--label=new.location-normalized.ll",
                             str(directory / "old.location-normalized.ll"), str(directory / "new.location-normalized.ll")],
                            capture_output=True, text=True)
    assert result.returncode == 1, (case["case"], result.returncode, result.stderr)
    diff = result.stdout
    (directory / "ir.location-normalized.diff").write_text(diff)
    added = [line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
    removed = [line[1:] for line in diff.splitlines() if line.startswith("-") and not line.startswith("---")]
    rows.append({"number": case["number"], "case": case["case"], "directory": case["directory"],
                 "changed_functions": case["changed_functions"], "additions": len(added), "removals": len(removed),
                 "declarations_only": bool(added or removed) and all(line.startswith("%C.") and " = type " in line for line in added + removed),
                 "declarations": added + removed if not case["changed_functions"] else [], "diff_bytes": len(diff.encode())})
(ROOT / "triage.json").write_text(json.dumps(rows, indent=2) + "\n")
constructor_ids = {85, 86, 110, 975, 1162, 2114, 2117, 1586, 1588, 1593, 2319, 2540, 2541}
constructors = [row for row in rows if row["declarations_only"] or row["number"] in constructor_ids or (row["number"] < 300 and row["number"] != 58)]
numeric = [row for row in rows if row not in constructors]
(ROOT / "constructor-review-cases.json").write_text(json.dumps(constructors, indent=2) + "\n")
(ROOT / "numeric-review-cases.json").write_text(json.dumps(numeric, indent=2) + "\n")
by_case = {row["case"]: row for row in summary["cases"]}
unchanged = []
for line in summary["location_substitutions"]:
    if line["allowed"]:
        continue
    directory = ROOT / by_case[line["case"]]["directory"]
    opposite = "old" if line["side"] == "new" else "new"
    other = (directory / (opposite + ".ll")).read_text().splitlines()
    item = {**line, "identical_line_present_in_other_ir": line["text"] in other,
            "explanation": "Shared candidate input/import search path, not compiler-private library; preserved verbatim."}
    assert item["identical_line_present_in_other_ir"], item
    unchanged.append(item)
(ROOT / "unchanged-home-payloads.json").write_text(json.dumps(unchanged, indent=2) + "\n")
print(json.dumps({"real_ir_cases": len(rows), "constructor_partition": len(constructors),
                  "numeric_partition": len(numeric), "declaration_only": sum(row["declarations_only"] for row in rows),
                  "unchanged_home_payloads": len(unchanged)}, indent=2))
