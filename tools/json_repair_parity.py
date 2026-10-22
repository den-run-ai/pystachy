"""Compare complete native/CPython replay output against the pinned oracle."""
import argparse
import json
from pathlib import Path
import sys


def normalize(value):
    if value[0] == "float-repr":
        return ["float", float(value[1]).hex()]
    if value[0] in ("list", "tuple"):
        return [value[0], [normalize(item) for item in value[1]]]
    if value[0] == "dict":
        return ["dict", [[normalize(key), normalize(item)] for key, item in value[1]]]
    return value


def exact_equal(left, right):
    # Python equality alone considers True == 1 and False == 0. Even payloads
    # inside our tags must retain their JSON types, including string code points.
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(exact_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(exact_equal(left[key], right[key]) for key in left)
    return left == right


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, nargs="?")
    local_cases = Path(__file__).with_name("cases.json")
    default_cases = local_cases if local_cases.exists() else Path(__file__).resolve().parents[1] / "tests/upstream/json_repair/cases.json"
    parser.add_argument("--cases", type=Path, default=default_cases)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--write-inputs", type=Path,
                        help="write replay inputs derived from the corpus; no second checked-in input copy is needed")
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text())
    if args.write_inputs:
        args.write_inputs.write_text("".join(json.dumps({key: row[key] for key in ("id", "api", "input", "flags")}, ensure_ascii=True) + "\n" for row in cases))
    if args.output is None:
        if args.write_inputs is None:
            parser.error("provide replay output or --write-inputs")
        return 0
    actual = {}
    problems = []
    for line_number, line in enumerate(args.output.read_text().splitlines(), 1):
        try:
            row = json.loads(line)
            ident = row.pop("id")
            if type(ident) is not int or ident in actual:
                raise ValueError("duplicate or non-integer case id")
            if "value" in row:
                row["value"] = normalize(row["value"])
            actual[ident] = row
        except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
            problems.append({"line": line_number, "error": str(exc)})
    expected_ids = {case["id"] for case in cases}
    for unexpected in sorted(set(actual) - expected_ids):
        problems.append({"id": unexpected, "error": "unexpected case id"})
    matches = 0
    for case in cases:
        ident = case["id"]
        if exact_equal(actual.get(ident), case["expected"]):
            matches += 1
        else:
            problems.append({"id": ident, "input": case["input"], "flags": case["flags"],
                             "sources": case["sources"], "expected": case["expected"],
                             "actual": actual.get(ident, {"error": "missing case"})})
    report = {"cases": len(cases), "matched": matches, "problems": problems}
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n")
    print(f"{matches}/{len(cases)} match; {len(problems)} problems")
    for problem in problems[:12]:
        print(json.dumps(problem, ensure_ascii=True))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
