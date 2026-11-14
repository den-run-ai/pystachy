"""Record every changed function and global for meaningful accepted-IR changes."""
import difflib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def functions(text):
    result = {}
    current = None
    lines = []
    outside = []
    for line in text.splitlines():
        if line.startswith("define "):
            assert current is None
            current = re.search(r"@([^\(]+)", line).group(1)
            lines = [line]
        elif current is not None:
            lines.append(line)
            if line == "}":
                result[current] = "\n".join(lines)
                current = None
        elif line:
            outside.append(line)
    assert current is None
    return result, outside


data = json.loads((ROOT / "classification.json").read_text())
rows = []
for case in data["results"]:
    if case["category"] != "meaningful IR change":
        continue
    path = Path(case["directory"])
    old = (path / "old.ll").read_text()
    new = (path / "new.ll").read_text()
    old_functions, old_globals = functions(old)
    new_functions, new_globals = functions(new)
    changed = [name for name in old_functions.keys() & new_functions.keys()
               if old_functions[name] != new_functions[name]]
    rows.append({"case": case["path"], "old_lines": len(old.splitlines()), "new_lines": len(new.splitlines()),
                 "changed_functions": sorted(changed), "added_functions": sorted(new_functions.keys() - old_functions.keys()),
                 "removed_functions": sorted(old_functions.keys() - new_functions.keys()),
                 "globals_changed": old_globals != new_globals,
                 "old_identity_mentions": old.count(".identity"), "new_identity_mentions": new.count(".identity")})
    difference = "\n".join(difflib.unified_diff(old_globals, new_globals, n=1))
    (path / "globals.raw.diff").write_text(difference + "\n")
(ROOT / "meaningful-ir-functions.json").write_text(json.dumps(rows, indent=2) + "\n")
print(json.dumps(rows, indent=2))
