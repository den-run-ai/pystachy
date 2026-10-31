#!/usr/bin/env python3
"""Fresh final-source preparation, with explicit reuse of immutable main/eca artifacts."""
import argparse
import ast
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import sys

import replay_support as replay

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parent
PRIOR = ROOT / "results-recovered-three"
CURRENT = WORK / "pystachy"

def stamp():
    return datetime.now(timezone.utc).isoformat()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-commit", required=True)
    parser.add_argument("--bootstrap", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(exist_ok=False)
    old_report = PRIOR / "measurement.json"
    old = json.loads(old_report.read_text())
    assert old["phases"]["prepare"]["status"] == "passed" and set(old["phases"]) == {"prepare"}
    identities = {name: old["source_identities"][name] for name in ("main", "eca")}
    identities["candidate"] = replay.source_identity(CURRENT)
    assert identities["candidate"]["commit"] == args.candidate_commit and identities["candidate"]["git_status"] == ""
    bootstrap_path = args.bootstrap.resolve()
    bootstrap = json.loads(bootstrap_path.read_text())
    assert bootstrap["status"] == "complete" and bootstrap["exit_code"] == 0 and bootstrap["source_identity_stable"]
    assert bootstrap["before"] == bootstrap["after"]
    for paths in (("pystachy", "build/pystachy1", "build/pystachy2"),
                  ("build/stage1.ll", "build/stage2.ll", "build/stage3.ll"),
                  ("build/rt1.ll", "build/rt2.ll", "build/rt3.ll")):
        assert len({bootstrap["artifacts"][path]["sha256"] for path in paths}) == 1, paths
    assert bootstrap["commit"] == args.candidate_commit and bootstrap["tree"] == identities["candidate"]["tree"]
    assert all(value == bootstrap["after"][path] for path, value in identities["candidate"]["input_sha256"].items() if path != "Makefile")
    assert identities["candidate"]["input_sha256"].keys() == old["source_identities"]["aaec"]["input_sha256"].keys()
    changed_inputs = [path for path, value in identities["candidate"]["input_sha256"].items() if value != old["source_identities"]["aaec"]["input_sha256"][path]]
    assert changed_inputs == ["src/pystachy_compiler/optimizations.py"]
    assert identities["candidate"]["input_sha256"][changed_inputs[0]] == "22e3a0ae01262b4f2c8520e70a0f603721ba7cfc713ddfc1edb21d7378187d95"
    native = CURRENT / "pystachy"
    assert replay.digest(native) == bootstrap["artifacts"]["pystachy"]["sha256"]
    assert replay.digest(WORK / "toolchain/manifest.json") == old["toolchain_manifest_sha256"]
    homes = {name: Path(identity["directory"]) for name, identity in identities.items()}
    compilers = {name: old["native_compilers"][name] for name in ("main", "eca")}
    compilers["candidate"] = {"path": str(native), "sha256": replay.digest(native), "bootstrap_record_sha256": replay.digest(bootstrap_path)}
    artifacts = {}
    for case, data in old["cases"].items():
        assert replay.digest(data["source"]) == data["source_sha256"]
        for name, row in data["frontend_ir"].items():
            artifacts[str(PRIOR / (name + "-" + case + ".ll"))] = row["sha256"]
            artifacts[str(PRIOR / (name + "-" + case + "-hosted.ll"))] = row["hosted_ir_sha256"]
        for name, row in data["builds"].items():
            artifacts[str(PRIOR / (name + "-" + case))] = row["sha256"]
        for name, row in old["equivalence"][case]["jit_optimized_bitcode"]["records"].items():
            for suffix, key in ((".bc", "sha256"), (".ll", "optimized_text_sha256"), ("-input.ll", "input_sha256")):
                artifacts[str(PRIOR / "jit-equivalence" / (name + "-" + case + suffix))] = row[key]
    def audit_prior():
        assert replay.digest(old_report) == result["prior_preparation"]["report_sha256"]
        for path, checksum in artifacts.items():
            assert replay.digest(path) == checksum, path
    llvm = Path(os.environ["PYSTACHY_LLVM"])
    vg = WORK / "toolchain/llvm18/usr"
    environment = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_") and key not in ("PYTHONPATH", "PYTHONHOME")}
    environment.update(PYSTACHY_LLVM=str(llvm), VALGRIND_LIB=str(vg / "libexec/valgrind"), PYTHONHASHSEED="0")
    envs = {name: dict(environment, PYSTACHY_HOME=str(home), PYSTACHY_CACHE=str(out / (name + "-cache"))) for name, home in homes.items()}
    def run(command, name="candidate", timeout=240, env=None):
        return replay.run(["taskset", "-c", "0", *map(str, command)], homes[name], env or envs[name], timeout)
    phase = {"status": "running", "started_utc": stamp(), "harness_sha256": replay.digest(Path(__file__)),
             "helper_sha256": replay.digest(ROOT / "replay_support.py"), "load_start": os.getloadavg()}
    result = {"purpose": __doc__, "started_utc": stamp(), "platform": platform.platform(), "cpuinfo": Path("/proc/cpuinfo").read_text(), "cpu": 0,
              "source_identities": identities, "native_compilers": compilers, "toolchain_manifest": old["toolchain_manifest"],
              "toolchain_manifest_sha256": old["toolchain_manifest_sha256"], "tools": old["tools"], "cases": {}, "phases": {"prepare": phase},
              "prior_preparation": {"path": str(old_report), "report_sha256": replay.digest(old_report), "audited_artifact_sha256": artifacts,
                                    "scope": "Original aaec preparation and its preserved failed descriptor-path assertion/resume remain unchanged. Existing main/eca artifacts and original probe paths are reused explicitly."},
              "candidate_bootstrap": {"path": str(bootstrap_path), "sha256": replay.digest(bootstrap_path),
                                      "complete_stable_manifest": True, "three_native_artifacts_identical": True,
                                      "compiler_and_runtime_three_stage_ir_fixed_points": True},
              "candidate_inputs_changed_from_aaec": changed_inputs, "equivalence": {}, "candidate_equivalence_to_aaec": {},
              "method": "Fresh final-source JSON counts/timings/native compile costs on recovered Intel host. Main/eca raw/AOT artifacts are reused byte-for-byte from the previous preparation; final candidate artifacts are regenerated. All original probe paths and runtime arguments are preserved. Six case labels/five unique source files, with four changed JSON labels/three unique source files timed. Historical AMD measurements remain separate."}
    def save():
        replay.save_json(out / "measurement.json", result)
    def verify():
        assert replay.digest(Path(__file__)) == phase["harness_sha256"]
        assert replay.digest(ROOT / "replay_support.py") == phase["helper_sha256"]
        for name, home in homes.items():
            assert replay.source_identity(home) == identities[name], name
            assert replay.digest(compilers[name]["path"]) == compilers[name]["sha256"], name
        audit_prior()
    replay_input = PRIOR / "jit-equivalence/prog.ll"
    replay_input_bytes = replay_input.read_bytes()
    try:
        verify()
        save()
        for name in ("main", "eca"):
            shutil.copytree(PRIOR / (name + "-cache"), out / (name + "-cache"))
        warm = out / "warm.py"
        warm.write_text("print(17)\n")
        result["runtime_warmups"] = {}
        for name in homes:
            row = run([compilers[name]["path"], "run", warm], name)
            assert row["stdout"] == "17\n"
            result["runtime_warmups"][name] = row
        for case, data in old["cases"].items():
            row = {key: deepcopy(data[key]) for key in ("source", "source_sha256", "n", "extra_untimed_kernel_calls", "extra_args", "cpython_oracle", "checksum")}
            row.update(frontend_ir={}, builds={}, runs={}, correctness={})
            result["cases"][case] = row
            for name in ("main", "eca"):
                if name not in data["frontend_ir"]:
                    continue
                for suffix, key in ((".ll", "frontend_ir"), ("", "builds")):
                    origin, target = PRIOR / (name + "-" + case + suffix), out / (name + "-" + case + suffix)
                    shutil.copy2(origin, target)
                    row[key][name] = {**deepcopy(data[key][name]), "reused_from": str(origin), "copied_artifact": str(target)}
                    assert replay.digest(target) == row[key][name]["sha256"]
            ir, executable = out / ("candidate-" + case + ".ll"), out / ("candidate-" + case)
            emission = run([native, "ir", row["source"], "-o", ir])
            emission.update(sha256=replay.digest(ir), ir_lines=len(ir.read_text().splitlines()))
            hosted = out / ("candidate-" + case + "-hosted.ll")
            run([sys.executable, "-m", "pystachy", "ir", row["source"], "-o", hosted])
            assert replay.digest(hosted) == emission["sha256"] == data["frontend_ir"]["aaec"]["sha256"], case
            emission["hosted_ir_sha256"] = replay.digest(hosted)
            row["frontend_ir"]["candidate"] = emission
            build = run([native, "build", row["source"], "-o", executable])
            build.update(sha256=replay.digest(executable), binary_bytes=executable.stat().st_size)
            assert build["sha256"] == data["builds"]["aaec"]["sha256"], case
            row["builds"]["candidate"] = build
            for mode, command in (("jit", [native, "run", row["source"]]), ("aot", [executable])):
                row["correctness"][mode] = replay.parse(run([*command, row["n"], *row["extra_args"]]), row["checksum"])
            result["candidate_equivalence_to_aaec"][case] = {"raw_ir": {"before_sha256": data["frontend_ir"]["aaec"]["sha256"], "after_sha256": emission["sha256"], "identical": True},
                                                           "aot_binary": {"before_sha256": data["builds"]["aaec"]["sha256"], "after_sha256": build["sha256"], "identical": True}}
            save()
            print("final prepared", case, flush=True)
        layout_values = {path.read_bytes() for path in (out / "candidate-cache").glob("*.target")}
        assert len(layout_values) == 1
        layout = next(iter(layout_values)).decode()
        old_layouts = {path.read_bytes() for path in (PRIOR / "aaec-cache").glob("*.target")}
        assert layout_values == old_layouts
        tree = ast.parse((CURRENT / "src/pystachy_compiler/lower_module.py").read_text())
        hooks = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "OBJHOOKS" for target in node.targets))
        capture, wrapper = out / "driver-proof", out / "driver-proof/llvm"
        wrapper.mkdir(parents=True)
        wrapper_text = '''#!PYTHON
import hashlib,json,os,stat,sys
from pathlib import Path
tool=Path(sys.argv[0]).name
destination=Path(os.environ["FINAL_DRIVER_PROOF"])
if tool == "opt":
 for value in sys.argv[1:]:
  if Path(value).name == "prog.ll" and Path(value).is_file():
   (destination/"actual-input.ll").write_bytes(Path(value).read_bytes())
   (destination/"opt-arguments.json").write_text(json.dumps(sys.argv[1:]))
if tool == "lli":
 parts=[]; offset=0
 while True:
  part=os.pread(8,1048576,offset)
  if not part: break
  parts.append(part); offset+=len(part)
 data=b"".join(parts); info=os.fstat(8)
 record={"arguments":sys.argv[1:],"runtime_fd8_sha256":hashlib.sha256(data).hexdigest(),"runtime_fd8_path":os.readlink("/proc/self/fd/8"),"regular_file":stat.S_ISREG(info.st_mode),"mode":oct(info.st_mode),"executable":os.access("/proc/self/fd/8",os.X_OK),"elf_magic":data[:4].hex(),"elf_type":int.from_bytes(data[16:18],"little")}
 (destination/"runtime-fd8.so").write_bytes(data)
 (destination/"lli.json").write_text(json.dumps(record))
os.execv(str(Path(LLVM)/tool),[str(Path(LLVM)/tool),*sys.argv[1:]])
'''.replace("#!PYTHON", "#!" + sys.executable).replace("LLVM", repr(str(llvm)))
        for tool in llvm.iterdir():
            target = wrapper / tool.name
            if tool.name in ("opt", "lli"):
                target.write_text(wrapper_text)
                target.chmod(0o755)
            else:
                target.symlink_to(tool)
        shutil.copytree(out / "candidate-cache", capture / "cache")
        capture_env = dict(envs["candidate"], PYSTACHY_LLVM=str(wrapper), PYSTACHY_CACHE=str(capture / "cache"), FINAL_DRIVER_PROOF=str(capture))
        probe = result["cases"]["json_calls"]
        proof_run = replay.parse(run([native, "run", probe["source"], probe["n"]], env=capture_env), probe["checksum"])
        assert (capture / "actual-input.ll").read_bytes() == (layout + (out / "candidate-json_calls.ll").read_text() + hooks).encode()
        actual = json.loads((capture / "lli.json").read_text())
        assert "-dlopen=/dev/fd/8" in actual["arguments"] and actual["regular_file"] and actual["executable"]
        assert actual["elf_magic"] == "7f454c46" and actual["elf_type"] == 3
        payloads = {replay.digest(path) for path in (out / "candidate-cache").glob("*.so")}
        assert actual["runtime_fd8_sha256"] in payloads
        result["actual_driver_proof"] = {"execution": proof_run, "actual_input_sha256": replay.digest(capture / "actual-input.ll"),
                                         "input_exactly_equals_target_raw_hooks": True, "opt_arguments": json.loads((capture / "opt-arguments.json").read_text()),
                                         "lli": actual, "matches_normal_runtime_payload": True,
                                         "scope": "Separate untimed actual-driver capture; inherited fd8 bytes verified before exec even if its temporary pathname is deleted."}
        jit = out / "jit-equivalence"
        jit.mkdir()
        for case, data in result["cases"].items():
            raw = (out / ("candidate-" + case + ".ll")).read_text()
            assert "@llvm.coro.id(" not in raw
            clean = "function(mem2reg,instcombine<no-verify-fixpoint>,simplifycfg)"
            if raw.count("\n") <= 20000:
                clean = "cgscc(inline," + clean + ")"
            pipeline = "globaldce,always-inline," + clean + ",function(early-cse,adce)"
            assert pipeline == old["equivalence"][case]["jit_optimized_bitcode"]["records"]["aaec"]["pipeline"]
            if case == "json_calls":
                assert "-passes=" + pipeline in result["actual_driver_proof"]["opt_arguments"]
            replay_input.write_text(layout + raw + hooks)
            shutil.copyfile(replay_input, jit / ("candidate-" + case + "-input.ll"))
            bc = jit / ("candidate-" + case + ".bc")
            row = run([llvm / "opt", "-passes=" + pipeline, replay_input, "-o", bc])
            row.update(sha256=replay.digest(bc), input_sha256=replay.digest(replay_input), pipeline=pipeline)
            expected = old["equivalence"][case]["jit_optimized_bitcode"]["after_sha256"]
            assert row["sha256"] == expected, case
            result["candidate_equivalence_to_aaec"][case]["jit_optimized_bitcode"] = {"before_sha256": expected, "after_sha256": row["sha256"], "identical": True, "record": row}
            result["equivalence"][case] = {}
            for kind, key in (("raw_ir", "frontend_ir"), ("aot_binary", "builds")):
                before, after = data[key]["eca"]["sha256"], data[key]["candidate"]["sha256"]
                result["equivalence"][case][kind] = {"before_sha256": before, "after_sha256": after, "identical": before == after}
            before = old["equivalence"][case]["jit_optimized_bitcode"]["before_sha256"]
            result["equivalence"][case]["jit_optimized_bitcode"] = {"before_sha256": before, "after_sha256": row["sha256"], "identical": before == row["sha256"]}
            result["equivalence"][case]["all_artifacts_identical"] = all(result["equivalence"][case][kind]["identical"] for kind in ("raw_ir", "aot_binary", "jit_optimized_bitcode"))
            save()
        replay_input.write_bytes(replay_input_bytes)
        result["replay_input_path"] = {"path": str(replay_input), "restored_byte_for_byte": replay_input.read_bytes() == replay_input_bytes,
                                         "scope": "Same original opt input pathname reused temporarily to preserve literal bitcode source identity, then restored; all named previous artifacts remain unchanged."}
        result["changed_cases"] = [case for case, data in result["equivalence"].items() if not data["all_artifacts_identical"]]
        result["unchanged_cases"] = [case for case, data in result["equivalence"].items() if data["all_artifacts_identical"]]
        assert result["changed_cases"] == old["changed_cases"]
        verify()
        phase["status"] = "passed"
        print("final preparation passed", result["changed_cases"], flush=True)
    except BaseException as error:
        phase.update(status="failed", error=repr(error), failure_record=getattr(error, "record", None))
        raise
    finally:
        replay_input.write_bytes(replay_input_bytes)
        phase.update(finished_utc=stamp(), load_end=os.getloadavg())
        save()

if __name__ == "__main__":
    main()
