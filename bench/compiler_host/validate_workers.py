"""Validate recorded worker artifacts and rejection paths without compiling.

--work is backend_scaling.py's work directory. Completed jobs are checked
offline; incomplete jobs are reported rather than silently counted as passes.
Negative controls use synthetic bytes, and subprocess execution is forbidden.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

import backend_workers as workers


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temp.replace(path)


def rejected(action, message):
    try:
        action()
    except RuntimeError as error:
        if message not in str(error):
            raise AssertionError(f"unexpected rejection: {error}") from error
        return {"passed": True, "error": str(error)}
    raise AssertionError("invalid worker artifact was accepted")


def inspect_job(directory, tool_identity, validate):
    job_file, result_file = directory / "job.json", directory / "result.json"
    job = json.loads(job_file.read_text())
    result = json.loads(result_file.read_text())
    expected = digest(job_file)
    if not result.get("complete"):
        raise RuntimeError("worker result is incomplete")
    if job["input_sha256"] != digest(directory / "input.bc"):
        raise RuntimeError("recorded input hash mismatch")
    if job["tool_sha256"] != tool_identity:
        raise RuntimeError("recorded tool identity differs from supplied LLVM")
    if result["job_sha256"] != expected:
        raise RuntimeError("recorded result belongs to another job")
    output = directory / "output.o"
    if result["output_sha256"] != digest(output) or result["output_bytes"] != output.stat().st_size:
        raise RuntimeError("recorded output hash/size mismatch")
    if validate is not None:
        validate(directory, expected)
    return {"passed": True, "job_sha256": expected,
            "input_sha256": job["input_sha256"], "output_sha256": result["output_sha256"],
            "output_bytes": result["output_bytes"]}


def negative_controls(root, llvm, tool_identity, validate):
    controls = {}

    def make_job(name):
        directory = root / name
        directory.mkdir()
        (directory / "input.bc").write_bytes(b"Synthetic validation input; not LLVM bitcode.\n")
        job = {"version": 1, "input_sha256": digest(directory / "input.bc"),
               "tool_sha256": tool_identity, "opt": 2, "emit": "object"}
        return directory, job

    for name, expected in (("wrong_input", "worker input/version mismatch"),
                           ("wrong_tool", "worker toolchain/options mismatch")):
        directory, job = make_job(name)
        if name == "wrong_input":
            job["input_sha256"] = "0" * 64
        else:
            job["tool_sha256"] = {key: "0" * 64 for key in tool_identity}
        write_json(directory / "job.json", job)
        control = rejected(lambda directory=directory: workers.worker(directory, llvm), expected)
        published = [name for name in ("result.json", "output.o", "output.tmp.o")
                     if (directory / name).exists()]
        if published:
            raise AssertionError(f"rejected worker published artifacts: {published}")
        control["no_published_output"] = True
        controls[name] = control

    if validate is None:
        controls["result_validation"] = {"passed": False, "unavailable":
            "backend_workers.validate_result(directory, expected_job_sha256) is missing"}
        return controls

    directory, job = make_job("result_binding")
    write_json(directory / "job.json", job)
    expected = digest(directory / "job.json")
    output = directory / "output.o"
    output.write_bytes(b"Synthetic object bytes; no compilation was run.\n")
    result = {"complete": True, "job_sha256": expected,
              "output_sha256": digest(output), "output_bytes": output.stat().st_size}
    write_json(directory / "result.json", result)
    validate(directory, expected)
    controls["valid_result"] = {"passed": True}

    # The expected identity belongs to the coordinator; trusting only the
    # worker's self-consistent report and output is insufficient.
    controls["wrong_expected_job"] = rejected(lambda: validate(directory, "0" * 64), "job")
    stale = dict(result, job_sha256="0" * 64)
    write_json(directory / "result.json", stale)
    controls["stale_result"] = rejected(lambda: validate(directory, expected), "job")
    write_json(directory / "result.json", result)
    output.write_bytes(output.read_bytes() + b"altered\n")
    controls["altered_output"] = rejected(lambda: validate(directory, expected), "output")
    return controls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    work, llvm = args.work.resolve(), args.llvm.resolve()
    jobs = sorted(path.parent for path in work.rglob("worker-*/job.json"))
    if not jobs:
        parser.error("no recorded worker job directories found")
    tool_identity = workers.identity(llvm)
    validate = getattr(workers, "validate_result", None)
    report = {"work": str(work), "llvm": str(llvm), "tool_sha256": tool_identity,
              "worker_script_sha256": digest(Path(workers.__file__)),
              "validation_script_sha256": digest(Path(__file__)),
              "result_validator_available": validate is not None,
              "records": [], "negative_controls": {}, "complete": False}
    attempted = []

    def forbid_execution(*arguments, **keywords):
        attempted.append(repr(arguments[0]) if arguments else "subprocess.run")
        raise AssertionError("validation attempted to execute a compiler subprocess")

    # Hashes and report checks must stay offline. This also proves that each
    # invalid worker job is rejected before reaching its first LLVM command.
    with patch.object(workers.subprocess, "run", side_effect=forbid_execution):
        for directory in jobs:
            record = {"directory": str(directory.relative_to(work)), "passed": False}
            try:
                record.update(inspect_job(directory, tool_identity, validate))
            except (OSError, ValueError, KeyError, RuntimeError) as error:
                record["error"] = str(error)
            report["records"].append(record)
        try:
            with tempfile.TemporaryDirectory(prefix="pystachy-worker-validation-") as temporary:
                report["negative_controls"] = negative_controls(Path(temporary), llvm, tool_identity, validate)
        except (OSError, ValueError, KeyError, RuntimeError, AssertionError) as error:
            report["negative_controls"]["failure"] = {"passed": False, "error": str(error)}
    report["compiler_subprocesses_attempted"] = attempted
    report["successful_jobs"] = sum(record["passed"] for record in report["records"])
    report["complete"] = (validate is not None and not attempted
                          and all(record["passed"] for record in report["records"])
                          and bool(report["negative_controls"])
                          and all(control["passed"] for control in report["negative_controls"].values()))
    write_json(args.report, report)
    print(json.dumps({"complete": report["complete"], "successful_jobs": report["successful_jobs"],
                      "recorded_jobs": len(jobs), "compiler_subprocesses_attempted": len(attempted)}))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
