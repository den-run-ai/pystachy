"""Find which substantive IR reviews can be reused from the preceding audit.

Only exact equal-length audit-home prefixes in generated location constants are
rewritten. No instruction, numeric constant, symbol, line number or type is
normalized. Both old and new complete IR and diagnostics must agree, as must the
case source, before an earlier review is reused. The full raw second run is still
retained independently.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def normalize_ir(data, mappings, substitutions):
    output = []
    for number, line in enumerate(data.splitlines(keepends=True), 1):
        for before, after in mappings:
            if before not in line:
                continue
            assert len(before) == len(after)
            import_path = (line.startswith(b"@s.") and b" = private unnamed_addr global " in line
                           and b'c"cannot import name ' in line
                           and re.search(rb" from '[^']+' \(" + re.escape(before) + rb"/(lib|ports|tests)/[A-Za-z0-9_./-]+\.py\)\\00\"\}, align 8\s*$", line))
            bare = (line.startswith(b"@s.") and b" = private unnamed_addr global " in line
                    and re.search(rb' c"' + re.escape(before) + rb'\\00"\}, align 8\s*$', line))
            allowed = bool(import_path or bare)
            substitutions.append({"line": number, "allowed": allowed, "text": line.decode().rstrip()})
            if allowed:
                line = line.replace(before, after)
        output.append(line)
    return b"".join(output)


def normalize_message(data, mappings):
    for before, after in mappings:
        home = re.escape(before) + rb"/lib/"
        location = rb"[A-Za-z0-9_./-]+\.py:[0-9]+"
        data = re.sub(rb"^" + home + rb"(" + location + rb": error:)", lambda m: after + b"/lib/" + m[1], data, flags=re.M)
        data = re.sub(rb"(for the call at )" + home + rb"(" + location + rb")", lambda m: m[1] + after + b"/lib/" + m[2], data)
        data = re.sub(rb"(<function [^\n]*? \()" + home + rb"(" + location + rb"\)>)", lambda m: m[1] + after + b"/lib/" + m[2], data)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path, required=True)
    args = parser.parse_args()
    previous = args.previous
    old = json.loads((previous / "final-summary.json").read_text())
    new = json.loads((ROOT / "summary.json").read_text())
    by_case = {row["case"]: row for row in old["cases"]}
    assert set(by_case) == {row["case"] for row in new["cases"]}
    for side in ("old", "new"):
        oldhome = previous / ("home-" + side)
        newhome = ROOT / ("home-" + side)
        assert len(str(oldhome)) == len(str(newhome))
    mappings = [(str(previous / ("home-" + side)).encode(), str(ROOT / ("home-" + side)).encode()) for side in ("old", "new")]
    all_rows = []
    for row in new["cases"]:
        earlier = by_case[row["case"]]
        if row["category"] in ("identical", "generated_home_only", "diagnostic_home_only"):
            continue
        result = {"number": row["number"], "case": row["case"], "category": row["category"],
                  "previous_category": earlier["category"], "same_source": row["source_sha256"] == earlier["source_sha256"],
                  "sides": {}, "location_substitutions": []}
        for side in ("old", "new"):
            left = previous / earlier["directory"]
            right = ROOT / row["directory"]
            li, ri = left / (side + ".ll"), right / (side + ".ll")
            if li.exists() and ri.exists():
                a = normalize_ir(li.read_bytes(), mappings, result["location_substitutions"])
                b = ri.read_bytes()
                irsame = a == b
                hashes = [sha(a), sha(b)]
            elif not li.exists() and not ri.exists():
                irsame = earlier[side + "_ir_sha256"] == row[side + "_ir_sha256"] == "missing"
                hashes = ["missing", "missing"]
            else:
                irsame = False
                hashes = []
            am = normalize_message((left / (side + ".msg")).read_bytes(), mappings)
            bm = (right / (side + ".msg")).read_bytes()
            result["sides"][side] = {"same_ir_after_demonstrated_home_replacement": irsame,
                                      "same_diagnostic": am == bm,
                                      "same_status": earlier[side + "_status"] == row[side + "_status"],
                                      "compared_ir_hashes": hashes}
        result["reusable_review"] = result["same_source"] and row["category"] == earlier["category"] and all(
            details["same_ir_after_demonstrated_home_replacement"] and details["same_diagnostic"] and details["same_status"]
            for details in result["sides"].values())
        all_rows.append(result)
    out = {"previous": str(previous), "current": str(ROOT), "equal_length_home_prefixes": True,
           "review_cases": len(all_rows), "reusable": sum(row["reusable_review"] for row in all_rows),
           "requires_review": [{key: row[key] for key in ("number", "case", "category", "previous_category")}
                               for row in all_rows if not row["reusable_review"]], "cases": all_rows}
    (ROOT / "comparison-previous.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({key: value for key, value in out.items() if key != "cases"}, indent=2))


if __name__ == "__main__":
    main()
