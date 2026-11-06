"""Profile LLVM passes on the same linked self-build module, separately from timings."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys

from backend_workers import LATE
from run import atomic_json, measure, sha


def rows(text):
    result = []
    # LLVM's report has user, system, total CPU and wall columns, each with a
    # percentage. Keep tables separate: analysis/pass totals are not additive.
    section = "unknown"
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if (0 < i < len(lines) - 1 and line.strip()
                and lines[i - 1].startswith("===") and lines[i + 1].startswith("===")):
            section = line.strip()
        fields = list(re.finditer(r"([0-9]+\.[0-9]+)\s+\(\s*[0-9.]+%\)", line))
        if len(fields) == 4:
            name = line[fields[-1].end():].strip()
            if name and name != "Total":
                result.append({"section": section, "name": name, "cpu_s": float(fields[2].group(1)), "wall_s": float(fields[3].group(1))})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    work, llvm = args.work.resolve(), args.llvm.resolve()
    work.mkdir(parents=True, exist_ok=False)
    source = args.snapshot.resolve() / "linked.bc"
    report = {"input_sha256": sha(source), "stages": {}, "complete": False}
    commands = [
        ("optimize", [str(llvm / "clang"), "-O2", "-c", "-emit-llvm", str(source), "-o", str(work / "optimized.bc"), "-ftime-report"]),
        ("late_inline", [str(llvm / "opt"), "-passes=forceattrs,always-inline", *LATE, str(work / "optimized.bc"), "-o", str(work / "late.bc")]),
        ("codegen", [str(llvm / "clang"), "-O2", "-c", "-Xclang", "-disable-llvm-passes", str(work / "late.bc"), "-o", str(work / "output.o"), "-ftime-report"]),
    ]
    for name, command in commands:
        result = measure.execute(command, dict(os.environ), 300)
        report["stages"][name] = result
        result["passes"] = rows(result["stderr"])
        atomic_json(args.report, report)
        measure.successful(result)
        if name != "late_inline" and not any(row["section"] == "Pass execution timing report" for row in result["passes"]):
            raise RuntimeError(f"LLVM emitted no parseable pass timers for {name}")
    report["ir_sizes"] = {}
    for name, file in (("linked", source), ("optimized", work / "optimized.bc"), ("late", work / "late.bc")):
        output = work / f"{name}.ll"
        result = measure.execute([str(llvm / "llvm-dis"), str(file), "-o", str(output)], dict(os.environ), 120)
        measure.successful(result)
        text = output.read_text()
        report["ir_sizes"][name] = {"bitcode_bytes": file.stat().st_size, "text_bytes": output.stat().st_size,
                                   "lines": text.count("\n"), "functions": len(re.findall(r"^define ", text, re.M)),
                                   "instructions_approx": len(re.findall(r"^  (?!;|\])\S", text, re.M))}
    report["output_object_sha256"] = sha(work / "output.o")
    report["input_unchanged"] = report["input_sha256"] == sha(source)
    report["complete"] = report["input_unchanged"]
    atomic_json(args.report, report)


if __name__ == "__main__":
    sys.exit(main())
