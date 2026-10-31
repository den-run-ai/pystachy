#!/usr/bin/env python3
"""Narrow resume: descriptor proof and optimized JIT comparison after preserved assertion failure."""
import ast
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys

import replay_support as replay

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parent
OUT = ROOT / "results-recovered-three"
report_path = OUT / "measurement.json"
result = json.loads(report_path.read_text())
assert result["phases"]["prepare"]["status"] == "failed"
archive = OUT / "failures/prepare-attempt1"
archive.mkdir(parents=True, exist_ok=False)
shutil.copy2(report_path, archive / "measurement.json")
shutil.copy2(ROOT / "measure_recovered.py", archive / "measure_recovered.py")
for name in ("actual-input.ll", "opt-arguments.json", "lli.json"):
    shutil.copy2(OUT / "driver-proof" / name, archive / name)
result.setdefault("prior_phase_attempts", []).append({"phase": "prepare", **result["phases"]["prepare"], "preserved_report_sha256": replay.digest(archive / "measurement.json")})
phase = {"status": "running", "started_utc": datetime.now(timezone.utc).isoformat(), "harness_sha256": {"finish_recovered_prepare.py": replay.digest(Path(__file__))},
         "resume_scope": "No compiler or AOT rebuild. Recheck source/native/prepared hashes, replace the pathname assertion by inherited-descriptor verification, finish JIT comparisons.",
         "correction": "The driver intentionally unlinks its temporary .so after opening fd8. A deleted pathname with a temporary suffix is valid shared-runtime provenance; checking suffix==.so and filesystem access after unlink was incorrect."}
result["phases"]["prepare"] = phase

def save():
    replay.save_json(report_path, result)

def verify():
    for name, identity in result["source_identities"].items():
        assert replay.source_identity(identity["directory"])["input_sha256"] == identity["input_sha256"]
        assert replay.digest(result["native_compilers"][name]["path"]) == result["native_compilers"][name]["sha256"]
    for case, data in result["cases"].items():
        assert replay.digest(data["source"]) == data["source_sha256"]
        for name, row in data["frontend_ir"].items():
            assert replay.digest(OUT / (name + "-" + case + ".ll")) == row["sha256"]
            assert replay.digest(OUT / (name + "-" + case + "-hosted.ll")) == row["hosted_ir_sha256"]
        for name, row in data["builds"].items():
            assert replay.digest(OUT / (name + "-" + case)) == row["sha256"]

llvm = Path(result["tools"]["llvm"])
home = Path(result["source_identities"]["aaec"]["directory"])
env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_") and key not in ("PYTHONPATH", "PYTHONHOME", "VALGRIND_LIB")}
env.update(PYSTACHY_LLVM=str(llvm), PYSTACHY_HOME=str(home), PYTHONHASHSEED="0")
def run(command, cwd=home, environment=env):
    return replay.run(["taskset", "-c", "0", *map(str, command)], cwd, environment, 240)

save()
try:
    verify()
    layout_values = {path.read_bytes() for path in (OUT / "aaec-cache").glob("*.target")}
    assert len(layout_values) == 1
    layout = next(iter(layout_values)).decode()
    tree = ast.parse((home / "src/pystachy_compiler/lower_module.py").read_text())
    hooks = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "OBJHOOKS" for target in node.targets))
    capture = OUT / "driver-proof-resume"
    capture.mkdir()
    wrapper = capture / "llvm"
    wrapper.mkdir()
    text = '''#!PYTHON
import hashlib,json,os,stat,struct,sys
from pathlib import Path
tool=Path(sys.argv[0]).name
destination=Path(os.environ["DRIVER_PROOF"])
if tool == "opt":
 for value in sys.argv[1:]:
  if Path(value).name == "prog.ll" and Path(value).is_file():
   (destination/"actual-input.ll").write_bytes(Path(value).read_bytes())
   (destination/"opt-arguments.json").write_text(json.dumps(sys.argv[1:]))
if tool == "lli":
 data=[]; offset=0
 while True:
  part=os.pread(8,1048576,offset)
  if not part: break
  data.append(part); offset+=len(part)
 payload=b"".join(data)
 info=os.fstat(8)
 (destination/"runtime-fd8.so").write_bytes(payload)
 record={"arguments":sys.argv[1:],"runtime_fd8_sha256":hashlib.sha256(payload).hexdigest(),"runtime_fd8_path":os.readlink("/proc/self/fd/8"),"fd8_is_regular_file":stat.S_ISREG(info.st_mode),"fd8_mode":oct(info.st_mode),"fd8_exec_access":os.access("/proc/self/fd/8",os.X_OK),"elf_magic":payload[:4].hex(),"elf_type":struct.unpack_from("<H",payload,16)[0]}
 (destination/"lli.json").write_text(json.dumps(record))
os.execv(str(Path(LLVM)/tool),[str(Path(LLVM)/tool),*sys.argv[1:]])
'''.replace("#!PYTHON", "#!" + sys.executable).replace("LLVM", repr(str(llvm)))
    for tool in llvm.iterdir():
        path = wrapper / tool.name
        if tool.name in ("opt", "lli"):
            path.write_text(text)
            path.chmod(0o755)
        else:
            path.symlink_to(tool)
    shutil.copytree(OUT / "aaec-cache", capture / "cache")
    capture_env = dict(env, PYSTACHY_LLVM=str(wrapper), PYSTACHY_CACHE=str(capture / "cache"), DRIVER_PROOF=str(capture))
    probe = result["cases"]["json_calls"]
    observed = replay.parse(run([result["native_compilers"]["aaec"]["path"], "run", probe["source"], probe["n"]], environment=capture_env), probe["checksum"])
    expected = (layout + (OUT / "aaec-json_calls.ll").read_text() + hooks).encode()
    assert (capture / "actual-input.ll").read_bytes() == expected
    actual = json.loads((capture / "lli.json").read_text())
    assert "-dlopen=/dev/fd/8" in actual["arguments"]
    assert actual["fd8_is_regular_file"] and actual["fd8_exec_access"]
    assert actual["elf_magic"] == "7f454c46" and actual["elf_type"] == 3
    assert replay.digest(capture / "runtime-fd8.so") == actual["runtime_fd8_sha256"]
    normal_hashes = {replay.digest(path) for path in (OUT / "aaec-cache").glob("*.so")}
    assert actual["runtime_fd8_sha256"] in normal_hashes, "captured runtime differs from normal cached runtime"
    result["actual_driver_proof"] = {"execution": observed, "actual_input_sha256": replay.digest(capture / "actual-input.ll"),
                                     "input_exactly_equals_target_raw_hooks": True, "opt_arguments": json.loads((capture / "opt-arguments.json").read_text()),
                                     "lli": actual, "matches_normal_runtime_payload": True,
                                     "scope": "Untimed actual native JIT capture. Hash and ELF/executable checks use inherited fd8 before exec; unlinked temporary pathname retained as observed."}
    save()
    jit = OUT / "jit-equivalence"
    jit.mkdir()
    for case in result["cases"]:
        records = {}
        for name in ("eca", "aaec"):
            raw = (OUT / (name + "-" + case + ".ll")).read_text()
            assert "@llvm.coro.id(" not in raw
            clean = "function(mem2reg,instcombine<no-verify-fixpoint>,simplifycfg)"
            if raw.count("\n") <= 20000:
                clean = "cgscc(inline," + clean + ")"
            pipeline = "globaldce,always-inline," + clean + ",function(early-cse,adce)"
            if case == "json_calls":
                assert "-passes=" + pipeline in result["actual_driver_proof"]["opt_arguments"]
            prog, bc = jit / "prog.ll", jit / (name + "-" + case + ".bc")
            prog.write_text(layout + raw + hooks)
            shutil.copyfile(prog, jit / (name + "-" + case + "-input.ll"))
            row = run([llvm / "opt", "-passes=" + pipeline, prog, "-o", bc], cwd=OUT)
            disassembly = jit / (name + "-" + case + ".ll")
            run([llvm / "opt", "-S", "-passes=verify", bc, "-o", disassembly], cwd=OUT)
            row.update(sha256=replay.digest(bc), input_sha256=replay.digest(prog), optimized_text_sha256=replay.digest(disassembly), pipeline=pipeline)
            records[name] = row
        result["equivalence"][case]["jit_optimized_bitcode"] = {"before_sha256": records["eca"]["sha256"], "after_sha256": records["aaec"]["sha256"],
                                                                   "identical": records["eca"]["sha256"] == records["aaec"]["sha256"], "records": records,
                                                                   "scope": "Exact bitcode bytes, same opt input path, verified actual driver target/hooks/pipeline."}
        result["equivalence"][case]["all_artifacts_identical"] = all(result["equivalence"][case][key]["identical"] for key in ("raw_ir", "aot_binary", "jit_optimized_bitcode"))
        save()
    result["changed_cases"] = [case for case, row in result["equivalence"].items() if not row["all_artifacts_identical"]]
    result["unchanged_cases"] = [case for case, row in result["equivalence"].items() if row["all_artifacts_identical"]]
    assert all(case.startswith("json") for case in result["changed_cases"])
    verify()
    phase["status"] = "passed"
    print(json.dumps({"changed_cases": result["changed_cases"], "unchanged_cases": result["unchanged_cases"], "driver_shared_runtime": actual}), flush=True)
except BaseException as error:
    phase.update(status="failed", error=repr(error), failure_record=getattr(error, "record", None))
    raise
finally:
    phase["finished_utc"] = datetime.now(timezone.utc).isoformat()
    save()
