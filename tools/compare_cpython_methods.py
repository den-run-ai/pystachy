"""Compare two CPython method triage reports on the same qualified method identities."""
import argparse
from collections import Counter
import json
from pathlib import Path


MATCHES = {"match", "match-python-int"}
OUTCOMES = MATCHES | {"differs", "compile-error", "timeout", "cpython-fail"}


def qualified_methods(report, *, oracle=False):
    if not isinstance(report, dict) or not isinstance(report.get("records"), list):
        raise ValueError("expected a report with a records list")
    if report.get("errors"):
        raise ValueError("report has extraction errors")
    seen = set()
    methods = {}
    for record in report["records"]:
        path = record["file"]
        name = record["test"]
        if not isinstance(path, str) or not path or not isinstance(name, str) or not name:
            raise ValueError("method records require a source path and test name")
        path = path.replace("\\", "/")
        # Existing triage reports can name the same pinned checkout by different absolute paths.
        _, marker, suffix = ("/" + path).rpartition("/Lib/test/")
        file = "Lib/test/" + suffix if marker else path
        key = file, name
        if key in seen:
            raise ValueError(f"duplicate method {file} {key[1]}")
        seen.add(key)
        status = record["cpython" if oracle else "status"]
        if status not in ({"ok", "fail"} if oracle else OUTCOMES):
            raise ValueError(f"unknown method status {status}")
        if status not in {"fail", "cpython-fail"}:
            methods[key] = status
    if not methods:
        raise ValueError("empty qualified method set")
    return methods


def select_cohort(report, selected, name):
    missing = selected.keys() - report.keys()
    if missing:
        raise ValueError(f"{name} lacks {len(missing)} qualified methods, including {min(missing)}")
    return {key: report[key] for key in selected}


def compare(before, after, qualification=None):
    prior = qualified_methods(before)
    current = qualified_methods(after)
    if qualification is not None:
        selected = qualified_methods(qualification, oracle=True)
        prior = select_cohort(prior, selected, "baseline")
        current = select_cohort(current, selected, "candidate")
    elif prior.keys() != current.keys():
        raise ValueError(f"qualification differs at {min(prior.keys() ^ current.keys())}; use identical method sets")
    gains, losses = [], []
    for key in sorted(prior):
        old, new = prior[key], current[key]
        if (old in MATCHES) != (new in MATCHES):
            changed = gains if new in MATCHES else losses
            changed.append({"file": key[0], "test": key[1], "before": old, "after": new})
    return {"qualified": len(prior), "before": dict(Counter(prior.values())), "after": dict(Counter(current.values())),
            "newly_matching": gains, "no_longer_matching": losses}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--qualification", type=Path, help="compare the successful method identities from a frozen CPython qualification report")
    args = parser.parse_args()
    try:
        qualification = json.loads(args.qualification.read_text()) if args.qualification else None
        result = compare(json.loads(args.before.read_text()), json.loads(args.after.read_text()), qualification)
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
