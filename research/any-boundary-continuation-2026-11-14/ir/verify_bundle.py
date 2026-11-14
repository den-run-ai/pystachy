"""Validate the retained audit evidence using only the Python standard library."""
from collections import Counter
import hashlib
import json
import lzma
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parent
HOME_CASES = {"tests/programs/library/lib_gettext.py", "tests/programs/library/sys_prefix.py"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def main():
    checksums = {}
    for line in (ROOT / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        assert name not in checksums
        assert file_digest(ROOT / name) == expected, name
        checksums[name] = expected
    actual = {str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file() and p.name != "SHA256SUMS"}
    assert actual == set(checksums), sorted(actual ^ set(checksums))
    summary = json.loads((ROOT / "summary.json").read_text())
    cases = [json.loads(line) for line in (ROOT / "case-results.jsonl").read_text().splitlines()]
    with lzma.open(ROOT / "source-identities.json.xz", "rt") as source:
        identities = json.load(source)
    assert len(cases) == summary["total_comparisons"] == 4650
    assert dict(Counter(row["category"] for row in cases)) == summary["counts"]
    assert {row["index"] for row in cases} == set(range(1, len(cases) + 1))
    assert not any(row["old_status"] == 0 and row["new_status"] != 0 for row in cases)
    assert sum(row["kind"] == "candidate" for row in cases) == 4649
    assert sum(bool(row["oracle_report"]) for row in cases) == summary["raw_oracle_difference_count"]
    source_check = json.loads((ROOT / "source-rechecked.json").read_text())
    for side in ("old", "new"):
        reconstructed = (json.dumps(identities[side], indent=2) + "\n").encode()
        assert digest(reconstructed) == source_check[side + "_identity_sha256"]
    assert {p: h for p, h in identities["old"]["source_files"].items() if p.startswith("lib/")} == {p: h for p, h in identities["new"]["source_files"].items() if p.startswith("lib/")}

    def normalize(data, installation=False):
        for identity in identities.values():
            prefix = identity["home"] + ("" if installation else "/lib/")
            data = data.replace(prefix.encode(), b"<PATH>")
        return data

    by_index = {row["index"]: row for row in cases}
    for row in cases:
        source = identities["new" if row["kind"] == "candidate" else "old"]
        assert row["source_ref"] == source["source_ref"]
        assert source["source_files"][row["path"]] == row["source_sha256"]
        for side in ("old", "new"):
            assert digest(row[side + "_message"].encode()) == row[side + "_message_sha256"]
        category = row["category"]
        if category == "improved acceptance":
            assert (row["old_status"], row["new_status"]) == (1, 0)
            assert row["new_message"] == ""
        else:
            assert row["old_status"] == row["new_status"]
            assert normalize(row["old_message"].encode()) == normalize(row["new_message"].encode())
        if category == "unchanged":
            assert row["old_ir_sha256"] == row["new_ir_sha256"]
        if category == "reviewed installation-path-only difference":
            assert row["path"] in HOME_CASES
        assert category in {"unchanged", "library-path-only difference", "reviewed installation-path-only difference",
                            "improved acceptance", "meaningful IR change"}

    wanted = json.loads((ROOT / "raw-files.json").read_text())
    seen = set()
    ir = {}

    def check_ir(index, values):
        row = by_index[index]
        for side, data in values.items():
            assert digest(data) == row[side + "_ir_sha256"]
            assert len(data) == row[side + "_ir_bytes"]
        if row["category"] in ("library-path-only difference", "reviewed installation-path-only difference"):
            if values:
                assert set(values) == {"old", "new"}
                whole_home = row["category"] == "reviewed installation-path-only difference"
                assert normalize(values["old"], whole_home) == normalize(values["new"], whole_home), row["path"]
            else:
                assert row["old_ir_sha256"] == row["new_ir_sha256"] == "missing"
        elif row["category"] == "meaningful IR change":
            assert set(values) == {"old", "new"}
            assert normalize(values["old"]) != normalize(values["new"])
        elif row["category"] == "improved acceptance":
            assert set(values) == {"new"}

    previous_index = None
    with tarfile.open(ROOT / "raw-changed-cases.tar.xz", "r:xz") as archive:
        for member in archive:
            assert member.isfile() and member.name in wanted and member.name not in seen
            data = archive.extractfile(member).read()
            assert len(data) == wanted[member.name]["bytes"]
            assert digest(data) == wanted[member.name]["sha256"]
            seen.add(member.name)
            _, case_index, name = member.name.split("/", 2)
            case_index = int(case_index)
            if previous_index is not None and previous_index != case_index:
                check_ir(previous_index, ir)
                ir = {}
            previous_index = case_index
            if name in ("old.ll", "new.ll"):
                ir[name.split(".")[0]] = data
    if previous_index is not None:
        check_ir(previous_index, ir)
    assert seen == set(wanted)
    assert {int(name.split("/")[1]) for name in seen} == {row["index"] for row in cases if row["oracle_report"]}
    print(f"Verified {len(cases)} case records, {len(seen)} raw archive members, all checksums, and every path-only classification.")


if __name__ == "__main__":
    main()
