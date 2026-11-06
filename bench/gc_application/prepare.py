#!/usr/bin/env python3
"""Generate deterministic application inputs from existing project fixtures.

Host-side preparation; run with CPython, before any benchmark measurement.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--records", type=int, default=20000)
    parser.add_argument("--customers", type=int, default=10000)
    args = parser.parse_args()
    if args.records < 1 or args.customers < 1:
        parser.error("records and customers must be positive")
    args.out.mkdir(parents=True, exist_ok=True)
    json_generator = ROOT / "tools/bench_json.py"
    traces_source = ROOT / "bench/json_repair/bench.py"
    mail_generator = ROOT / "examples/mailmerge/gendata.py"
    fixture = load_module("application_json_fixture", json_generator)
    records = args.out / "records.json"
    records.write_text(fixture.fixture(args.records, "changing", "utf8") + "\n", encoding="utf-8")
    tree = ast.parse(traces_source.read_text(encoding="utf-8"))
    assignments = [node for node in tree.body if isinstance(node, ast.AnnAssign)
                   and isinstance(node.target, ast.Name) and node.target.id == "SOURCES"]
    if len(assignments) != 1:
        raise ValueError("expected one annotated SOURCES fixture in the existing repair benchmark")
    sources = ast.literal_eval(assignments[0].value)
    if not isinstance(sources, list) or not sources or not all(isinstance(s, str) for s in sources):
        raise ValueError("expected a nonempty list of repair source strings")
    repairs = args.out / "repair-inputs.jsonl"
    repairs.write_text("".join(json.dumps(s, ensure_ascii=True) + "\n" for s in sources), encoding="utf-8")
    generator = load_module("application_mail_fixture", mail_generator)
    mail = args.out / "customers.tsv"
    with mail.open("w", encoding="utf-8", newline="") as stream:
        stream.write("\t".join(generator.FIELDS) + "\n")
        for index in range(args.customers):
            stream.write("\t".join(generator.record(index)) + "\n")
    manifest = {
        "records": args.records,
        "record_profile": "changing",
        "record_text": "utf8",
        "customers": args.customers,
        "repair_sources": len(sources),
        "generator_sources_sha256": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in (Path(__file__).resolve(), json_generator, traces_source, mail_generator)
        },
        "inputs": {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
                   for path in (records, repairs, mail)},
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
