#!/usr/bin/env python3
"""Bounded actual-driver optimizer/lli instruction attribution; no elapsed acceptance series."""
import argparse
from datetime import datetime, timezone
import difflib
import json
import os
from pathlib import Path
import shutil
import sys

import profile_native_frontend as profile
import replay_support as replay

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parent
OUT = ROOT / "backend-attribution-da84"
FINAL = ROOT / "results-final-da84/measurement.json"
OLD_HOME = WORK / "baselines/old-eca"

def stamp():
    return datetime.now(timezone.utc).isoformat()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("opt", "lli"))
    parser.add_argument("--lli-justification", default="")
    args = parser.parse_args()
    assert replay.digest(FINAL) == "adddef35dede86bf36d3b064dee9fb09bed4a2d2dd0e4076030960cf77b37595"
    data = json.loads(FINAL.read_text())
    assert set(data["phases"]) == {"prepare", "counts", "timings", "compile"}
    assert all(row["status"] == "passed" for row in data["phases"].values())
    homes = {name: Path(data["source_identities"][name]["directory"]) for name in ("main", "candidate")}
    source = OLD_HOME / "bench/smoke/text.py"
    sys.path.insert(0, str(OLD_HOME / "tools"))
    from bench_pyperformance import run as smoke_run
    llvm = Path(os.environ["PYSTACHY_LLVM"])
    vg = WORK / "toolchain/llvm18/usr"
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_") and key not in ("PYTHONPATH", "PYTHONHOME", "VALGRIND_LIB")}
    env.update(PYTHONHASHSEED="0", VALGRIND_LIB=str(vg / "libexec/valgrind"), ATTR_REAL_LLVM=str(llvm), ATTR_VALGRIND=str(vg / "bin/valgrind"))
    os.sched_setaffinity(0, {0})
    inputs = [Path(__file__), ROOT / "backend_tool_wrapper.py", ROOT / "replay_support.py", ROOT / "profile_native_frontend.py",
              OLD_HOME / "tools/bench_pyperformance.py", OLD_HOME / "tools/bench_extended.py", source, WORK / "toolchain/manifest.json", FINAL]
    if args.phase == "opt":
        OUT.mkdir(exist_ok=False)
        report = {"purpose": __doc__, "status": "incomplete", "started_utc": stamp(), "source_identities": {name: data["source_identities"][name] for name in homes},
                  "native_compilers": {name: data["native_compilers"][name] for name in homes}, "input_sha256": {str(path): replay.digest(path) for path in inputs},
                  "cpu": 0, "arguments": ["fnmatch", "1000"], "source": str(source), "phases": {}, "observations": {},
                  "scope": "One normal actual-driver capture and one opt profile per main/final variant. At most one subsequent lli profile each if opt leaves dominant startup work unexplained. Whole opt/lli processes include loading/initialization/teardown; lli also includes JIT code generation and executed program/runtime/GC. Instrumentation environment and inlining limit causal attribution. No real-hardware cycle or elapsed-acceptance claim.",
                  "timing_scope": "Tool wall observations are diagnostic, with a subprocess wrapper; they are not a timing series or normal-driver performance acceptance."}
    else:
        report = json.loads((OUT / "report.json").read_text())
        assert report["phases"]["opt"]["status"] == "passed" and args.lli_justification
        report["lli_justification"] = args.lli_justification
    def save():
        replay.save_json(OUT / "report.json", report)
    def verify():
        for path, expected in report["input_sha256"].items():
            assert replay.digest(path) == expected, path
        for name, home in homes.items():
            assert replay.source_identity(home) == report["source_identities"][name], name
            assert replay.digest(report["native_compilers"][name]["path"]) == report["native_compilers"][name]["sha256"]
    assert args.phase not in report["phases"]
    phase = {"status": "running", "started_utc": stamp()}
    report["phases"][args.phase] = phase
    save()
    wrapper = OUT / "llvm"
    envs = {name: dict(env, PYSTACHY_HOME=str(home), PYSTACHY_LLVM=str(wrapper), PYSTACHY_CACHE=str(OUT / (name + "-cache"))) for name, home in homes.items()}
    def disassemble(path):
        target = path.with_suffix(".ll")
        replay.run([llvm / "llvm-dis", path, "-o", target], OUT, env, 60)
        return target.read_text(), target
    def compare_outputs(normal_dir, measured_dir, normal, measured):
        assert normal["opt"]["input_sha256"] == measured["opt"]["input_sha256"]
        def normalized_args(row):
            return ["INPUT" if value == row["input_path"] else "OUTPUT" if value == row["output_path"] else value for value in row["arguments"]]
        assert normalized_args(normal["opt"]) == normalized_args(measured["opt"])
        assert normal["lli"]["arguments"] == measured["lli"]["arguments"]
        assert normal["lli"]["fd8"]["sha256"] == measured["lli"]["fd8"]["sha256"]
        assert measured["opt"]["output_sha256"] == measured["lli"]["fd9"]["sha256"]
        before, after = normal_dir / "optimized-output.bc", measured_dir / "optimized-output.bc"
        equality = {"literal_bitcode_equal": before.read_bytes() == after.read_bytes(), "actual_input_identical": True,
                    "same_flags_and_runtime_bytes": True, "normal_bitcode_sha256": replay.digest(before), "profile_bitcode_sha256": replay.digest(after)}
        if not equality["literal_bitcode_equal"]:
            left, left_path = disassemble(before)
            right, right_path = disassemble(after)
            def body(text, row, bc_path):
                lines = text.splitlines(keepends=True)
                module = [line for line in lines if line.startswith("; ModuleID = ")]
                filename = [line for line in lines if line.startswith("source_filename = ")]
                assert len(module) == len(filename) == 1
                assert module[0].strip() == "; ModuleID = '" + str(bc_path) + "'"
                assert filename[0].strip() == "source_filename = " + json.dumps(row["opt"]["input_path"])
                return [line for line in lines if not line.startswith(("; ModuleID = ", "source_filename = "))]
            assert body(left, normal, before) == body(right, measured, after), "optimized body differs beyond proven path headers"
            diff = "".join(difflib.unified_diff(left.splitlines(keepends=True), right.splitlines(keepends=True), fromfile=str(left_path), tofile=str(right_path)))
            (measured_dir / "normal-vs-profile.diff").write_text(diff)
            equality.update(only_demonstrated_path_headers_differ=True, raw_diff=diff, diff_sha256=replay.digest(measured_dir / "normal-vs-profile.diff"),
                            normal_text_sha256=replay.digest(left_path), profile_text_sha256=replay.digest(right_path))
        return equality
    try:
        verify()
        if args.phase == "opt":
            wrapper.mkdir()
            script = (ROOT / "backend_tool_wrapper.py").read_text().replace("#!/usr/bin/env python3", "#!" + sys.executable, 1)
            for tool in llvm.iterdir():
                target = wrapper / tool.name
                if tool.name in ("opt", "lli"):
                    target.write_text(script)
                    target.chmod(0o755)
                else:
                    target.symlink_to(tool)
            report["generated_wrapper_sha256"] = replay.digest(wrapper / "opt")
            assert replay.digest(wrapper / "lli") == report["generated_wrapper_sha256"]
            for name in homes:
                shutil.copytree(ROOT / "results-final-da84" / (name + "-cache"), OUT / (name + "-cache"))
            warm = OUT / "warm.py"
            warm.write_text("print(17)\n")
            report["warmups"] = {}
            for name in homes:
                row = replay.run([report["native_compilers"][name]["path"], "run", warm], homes[name], envs[name], 120)
                assert row["stdout"] == "17\n"
                report["warmups"][name] = row
            report["oracle"] = smoke_run([sys.executable, str(source), *report["arguments"]], env, 60)
            save()
        stages = ("normal", "opt") if args.phase == "opt" else ("lli",)
        for stage in stages:
            for name in homes:
                directory = OUT / (stage + "-" + name)
                directory.mkdir()
                actual_env = dict(envs[name], ATTR_DIRECTORY=str(directory), ATTR_STAGE=stage)
                command = [report["native_compilers"][name]["path"], "run", str(source), *report["arguments"]]
                execution = smoke_run(command, actual_env, 360, report["oracle"]["stdout"])
                observation = {"command": command, "execution": execution,
                               "opt": json.loads((directory / "opt.json").read_text()), "lli": json.loads((directory / "lli.json").read_text())}
                assert observation["opt"]["returncode"] == observation["lli"]["returncode"] == 0
                assert observation["opt"]["output_sha256"] == observation["lli"]["fd9"]["sha256"]
                assert observation["lli"]["fd8"]["regular_file"] and observation["lli"]["fd9"]["regular_file"]
                expected_runtime_payloads = {replay.digest(path) for path in (ROOT / "results-final-da84" / (name + "-cache")).glob("*.so")}
                assert expected_runtime_payloads and observation["lli"]["fd8"]["sha256"] in expected_runtime_payloads
                observation["runtime_matches_frozen_final_cache"] = True
                report["observations"][stage + "_" + name] = observation
                if stage != "normal":
                    normal = report["observations"]["normal_" + name]
                    observation["equivalence"] = compare_outputs(OUT / ("normal-" + name), directory, normal, observation)
                    raw_profile = directory / (stage + ".callgrind")
                    observation["profile_sha256"] = replay.digest(raw_profile)
                    observation["attribution"] = profile.parse_profile(raw_profile)
                    observation["valgrind_log"] = (directory / (stage + "-valgrind.log")).read_text()
                    print("backend profiled", stage, name, observation["attribution"]["total_instructions"], flush=True)
                else:
                    print("backend normal captured", name, observation["opt"]["observed_tool_wall_s"], observation["lli"]["observed_tool_wall_s"], flush=True)
                save()
        verify()
        assert replay.digest(wrapper / "opt") == replay.digest(wrapper / "lli") == report["generated_wrapper_sha256"]
        phase["status"] = "passed"
        report["status"] = "opt_complete" if args.phase == "opt" else "complete"
    except BaseException as error:
        phase.update(status="failed", error=repr(error), failure_record=getattr(error, "record", None))
        report["status"] = "failed"
        raise
    finally:
        phase["finished_utc"] = stamp()
        save()

if __name__ == "__main__":
    main()
