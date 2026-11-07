"""Classify preserved irsame differences without changing its outcome."""
import hashlib
import json
from pathlib import Path
import re


RUN = Path(__file__).resolve().parent
manifest = json.loads((RUN / "manifest.json").read_text())
old_prefix = (manifest["baseline_home"] + "/lib/").encode()
new_prefix = (manifest["candidate_home"] + "/lib/").encode()
old_home = manifest["baseline_home"].encode()
new_home = manifest["candidate_home"].encode()

# Only the compiler's complete global Str constant shape qualifies. All
# non-payload syntax, identity, flags, and alignment must remain identical.
constant = re.compile(
    rb'(?P<begin>@s\.\d+ = private unnamed_addr global \{i64, i64, i64, \[)'
    rb'(?P<size1>\d+)(?P<a> x i8\]\} \{i64 )(?P<length>\d+)'
    rb'(?P<flags>, i64 \d+, i64 )(?P<size2>\d+)'
    rb'(?P<b>, \[)(?P<size3>\d+)(?P<c> x i8\] c")'
    rb'(?P<payload>[^"\n]*)(?P<end>"\}, align 8\n?)'
)


def unescape(payload):
    output = bytearray()
    position = 0
    while position < len(payload):
        value = payload[position]
        if value == 92:
            escape = payload[position + 1:position + 3]
            if len(escape) != 2 or not all(c in b"0123456789abcdefABCDEF" for c in escape):
                raise ValueError("unexpected LLVM string escape")
            output.append(int(escape, 16))
            position += 3
        else:
            output.append(value)
            position += 1
    return bytes(output)


def path_constant(old, new):
    left, right = constant.fullmatch(old), constant.fullmatch(new)
    if left is None or right is None:
        return None
    for key in ("begin", "a", "flags", "b", "c", "end"):
        if left[key] != right[key]:
            return None
    before, after = unescape(left["payload"]), unescape(right["payload"])
    if before == old_home + b"\0" and after == new_home + b"\0":
        # builtins.gen_modattr emits Gen.prefix for sys.*prefix. Both
        # library/sys_prefix.py and lib/gettext.py exercise this exact value.
        origin = "sys_prefix"
    elif old_prefix in before and new_prefix in after and before.replace(old_prefix, new_prefix) == after:
        origin = "library_path"
    else:
        return None
    for match, content in ((left, before), (right, after)):
        if not content.endswith(b"\0") or int(match["length"]) != len(content) - 1:
            return None
        if any(int(match[key]) != len(content) for key in ("size1", "size2", "size3")):
            return None
    return {"symbol": left["begin"].decode().split()[0], "origin": origin,
            "old_payload": before[:-1].decode("utf-8"),
            "new_payload": after[:-1].decode("utf-8"),
            "old_size": len(before), "new_size": len(after)}


def diagnostic_locations(old, new):
    # These observed diagnostics retain their exact wording and line numbers.
    # The default oracle deliberately leaves them raw because prose includes
    # apostrophes; classify only the actual location shapes, never quoted data.
    pattern = re.compile(rb'(^| for the call at )' + re.escape(old_prefix)
                         + rb'([A-Za-z0-9_./-]+\.py:[0-9]+)', re.MULTILINE)
    matches = list(pattern.finditer(old))
    if not matches or len(matches) != old.count(old_prefix):
        return None
    replaced = pattern.sub(lambda match: match[1] + new_prefix + match[2], old)
    if replaced != new:
        return None
    return [match[2].decode() for match in matches]


records = []
for index, case in enumerate(manifest["cases"], 1):
    directory = RUN / "capture" / str(index)
    report_file = directory / "report"
    if not report_file.is_file():
        records.append({"case": case, "category": "missing_result"})
        continue
    report = report_file.read_text()
    if not report:
        records.append({"case": case, "category": "exact_tool_match"})
        continue
    record = {"case": case, "artifact_directory": str(directory), "tool_report": report}
    if "exit status" in report or "  messages:" in report or "IR written by only one" in report:
        record["category"] = "diagnostic_or_status_change"
        if "exit status" not in report and not (directory / "old.ll").exists() and not (directory / "new.ll").exists():
            locations = diagnostic_locations((directory / "old.msg").read_bytes(),
                                             (directory / "new.msg").read_bytes())
            if locations is not None:
                record["category"] = "diagnostic_paths_only"
                record["diagnostic_locations"] = locations
        if (case == "tests/deviations/ctypes_pointer_range.py"
                and "  exit status 1 -> 0\n" in report
                and not (directory / "old.ll").exists()
                and (directory / "new.ll").is_file()
                and (directory / "new.msg").read_bytes() == b""):
            record["category"] = "expected_ctypes_acceptance"
    else:
        old = (directory / "old.ll").read_bytes().splitlines(keepends=True)
        new = (directory / "new.ll").read_bytes().splitlines(keepends=True)
        literals = []
        unexplained = []
        if len(old) != len(new):
            unexplained.append({"line_counts": [len(old), len(new)]})
        else:
            for line, (before, after) in enumerate(zip(old, new), 1):
                if before == after:
                    continue
                literal = path_constant(before, after)
                if literal is None:
                    unexplained.append({"line": line, "old": before.decode("utf-8"),
                                        "new": after.decode("utf-8")})
                else:
                    literals.append({"line": line, **literal})
        record["path_constants"] = literals
        record["unexplained"] = unexplained
        record["category"] = "path_constants_only" if literals and not unexplained else "other_ir_change"
    record["artifacts_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(directory.iterdir()) if p.is_file()}
    records.append(record)

counts = {}
for record in records:
    counts[record["category"]] = counts.get(record["category"], 0) + 1
summary = {"counts": counts,
           "raw_tool_status": json.loads((RUN / "status.json").read_text()) if (RUN / "status.json").exists() else None,
           "classification_rule": "Only complete compiler Str constants; exact baseline/lib to candidate/lib payload replacement, or the complete emitted sys.*prefix value from each compiler's home. All other bytes identical, every embedded size validated against decoded bytes. Rejection diagnostics are path-only only when every replaced library prefix is at a primary source-location line start or 'for the call at' location and exact wording and line numbers match. No normalized rerun or success reclassification.",
           "records": records}
(RUN / "classification.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(counts, indent=2))
for record in records:
    if record["category"] in ("diagnostic_or_status_change", "other_ir_change"):
        print(record["case"], record["category"])
        print(record["tool_report"])
