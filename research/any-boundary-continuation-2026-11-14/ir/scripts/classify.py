"""Verify retained comparison evidence and classify every completed case."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REVIEWED_HOME_PATH_CASES = {
    "tests/programs/library/lib_gettext.py":
        "lib/gettext.py:62 uses sys.base_prefix for the default locale directory; "
        "src/pystachy_compiler/builtins.py:145-148 emits self.prefix. "
        "The complete raw diff contains only this installation prefix and the library import-error location.",
    "tests/programs/library/sys_prefix.py":
        "The fixture directly reads all four sys installation prefixes; "
        "src/pystachy_compiler/builtins.py:145-148 emits self.prefix. "
        "The complete raw diff changes only the one installation-prefix string constant.",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--complete", action="store_true")
    args = parser.parse_args()
    records = {key: json.loads((ROOT / (key + "-identity.json")).read_text()) for key in ("old", "new")}
    cases = json.loads((ROOT / "audit-cases.json").read_text())
    roots = list((ROOT / "retained").glob("pystachy-irsame.*"))
    assert len(roots) == 1, roots
    retained = roots[0]
    old_lib = {p: h for p, h in records["old"]["source_files"].items() if p.startswith("lib/")}
    new_lib = {p: h for p, h in records["new"]["source_files"].items() if p.startswith("lib/")}
    assert old_lib == new_lib

    def normalize_lib(data):
        for record in records.values():
            data = data.replace((record["home"] + "/lib/").encode(), b"<COMPILER_LIB>/")
        return data

    def normalize_home(data):
        for record in records.values():
            data = data.replace(record["home"].encode(), b"<FROZEN_COMPILER_HOME>")
        return data

    results = []
    pending = []
    for index, case in enumerate(cases, 1):
        directory = retained / str(index)
        if not (directory / "report").is_file():
            pending.append(case["argument"])
            continue
        assert (directory / "case").read_text().strip() == case["argument"]
        assert (directory / "source.sha256").read_text().split()[0] == case["source_sha256"]
        result = {**case, "index": index, "directory": str(directory)}
        messages = {}
        ir = {}
        for side in records:
            status = int((directory / (side + ".status")).read_text().strip())
            result[side + "_status"] = status
            message = (directory / (side + ".msg")).read_bytes()
            assert sha(message) == (directory / (side + ".msg.sha256")).read_text().split()[0]
            result[side + "_message"] = message.decode()
            normal = directory / (side + ".normal.msg")
            messages[side] = normal.read_bytes() if normal.exists() else message
            ir_path = directory / (side + ".ll")
            result[side + "_ir_sha256"] = (directory / (side + ".ir.sha256")).read_text().split()[0]
            result[side + "_ir_bytes"] = int((directory / (side + ".ir.bytes")).read_text())
            if ir_path.exists():
                data = ir_path.read_bytes()
                assert sha(data) == result[side + "_ir_sha256"]
                assert len(data) == result[side + "_ir_bytes"]
                ir[side] = data
                result[side + "_lib_normalized_ir_sha256"] = sha(normalize_lib(data))
                result[side + "_home_normalized_ir_sha256"] = sha(normalize_home(data))
        report = (directory / "report").read_text()
        result["oracle_report"] = report
        result["raw_messages_equal"] = result["old_message"] == result["new_message"]
        result["raw_ir_equal"] = result["old_ir_sha256"] == result["new_ir_sha256"]
        old_status = result["old_status"]
        new_status = result["new_status"]
        if not report:
            assert old_status == new_status
            assert result["raw_ir_equal"]
            assert messages["old"] == messages["new"]
            category = "unchanged"
        elif old_status == 0 and new_status != 0:
            category = "new rejection"
        elif old_status != 0 and new_status == 0:
            category = "improved acceptance"
        elif old_status != new_status:
            category = "changed failure status"
        elif (result["raw_ir_equal"] or len(ir) == 2 and normalize_lib(ir["old"]) == normalize_lib(ir["new"])) and normalize_lib(messages["old"]) == normalize_lib(messages["new"]):
            category = "library-path-only difference"
        elif len(ir) == 2 and normalize_home(ir["old"]) == normalize_home(ir["new"]) and normalize_home(messages["old"]) == normalize_home(messages["new"]):
            if case["path"] in REVIEWED_HOME_PATH_CASES:
                category = "reviewed installation-path-only difference"
                result["path_review"] = REVIEWED_HOME_PATH_CASES[case["path"]]
            else:
                category = "unreviewed installation-path-only difference"
        elif old_status != 0:
            category = "changed rejection diagnostic"
        elif normalize_lib(messages["old"]) != normalize_lib(messages["new"]):
            category = "changed accepted diagnostic"
        else:
            category = "meaningful IR change"
        result["category"] = category
        results.append(result)

    assert not args.complete or not pending, pending[:10]
    result = {"baseline_ref": records["old"]["source_ref"], "candidate_ref": records["new"]["source_ref"],
              "baseline_corpus_count": len(records["old"]["cases"]), "candidate_corpus_count": len(records["new"]["cases"]),
              "total_comparisons": len(cases), "completed": len(results), "pending": len(pending),
              "libraries_byte_identical": True,
              "normalization": "Exact old/new frozen compiler lib prefixes, plus separately reviewed installation prefixes in an explicit case allowlist; all source files were checked not to contain either frozen-home path",
              "counts": dict(Counter(r["category"] for r in results)),
              "candidate_counts": dict(Counter(r["category"] for r in results if r["kind"] == "candidate")),
              "supplemental_counts": dict(Counter(r["category"] for r in results if r["kind"] != "candidate")),
              "results": results}
    name = "classification.json" if args.complete else "classification-progress.json"
    (ROOT / name).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "results"}, indent=2))
    print(json.dumps([{k: r[k] for k in ("path", "kind", "old_status", "new_status", "category", "directory")}
                      for r in results if r["category"] not in ("unchanged", "library-path-only difference", "reviewed installation-path-only difference")], indent=2))


if __name__ == "__main__":
    main()
