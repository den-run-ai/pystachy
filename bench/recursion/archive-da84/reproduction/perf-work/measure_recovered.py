#!/usr/bin/env python3
"""Fresh Intel-host native JSON follow-up; old AMD measurements remain historical."""
import argparse
import ast
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import sys

import count_support
import replay_support as replay

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parent
HOMES = {"main": WORK / "baselines/main", "eca": WORK / "baselines/old-eca", "aaec": WORK / "pystachy"}
BOOTSTRAPS = {"main": "main", "eca": "old-eca", "aaec": "candidate"}

def stamp():
    return datetime.now(timezone.utc).isoformat()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "counts", "timings", "compile"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    llvm = Path(os.environ["PYSTACHY_LLVM"])
    vg = WORK / "toolchain/llvm18/usr"
    environment = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_") and key not in ("PYTHONPATH", "PYTHONHOME")}
    environment.update(PYSTACHY_LLVM=str(llvm), VALGRIND_LIB=str(vg / "libexec/valgrind"), PYTHONHASHSEED="0")
    envs = {name: dict(environment, PYSTACHY_HOME=str(home), PYSTACHY_CACHE=str(out / (name + "-cache"))) for name, home in HOMES.items()}
    def run(command, cwd, env, timeout=240):
        return replay.run(["taskset", "-c", "0", *map(str, command)], cwd, env, timeout)
    if args.phase == "prepare":
        out.mkdir(exist_ok=False)
        result = {"purpose": __doc__, "started_utc": stamp(), "platform": platform.platform(), "cpuinfo": Path("/proc/cpuinfo").read_text(), "cpu": 0,
                  "source_identities": {name: replay.source_identity(home) for name, home in HOMES.items()}, "native_compilers": {},
                  "toolchain_manifest": json.loads((WORK / "toolchain/manifest.json").read_text()), "toolchain_manifest_sha256": replay.digest(WORK / "toolchain/manifest.json"),
                  "tools": {"python": sys.executable, "llvm": str(llvm), "valgrind_root": str(vg)}, "cases": {}, "phases": {}, "equivalence": {},
                  "method": "Fresh native main/eca/aaec artifacts on the recovered Intel host/toolchain. Exact same probe bytes and paths within this new series. Six-case eca/aaec raw LLVM, driver-faithful JIT bitcode and AOT comparison; only changed cases are timed/counted. Six rotated process rounds, seven measured calls each; three rotated native compilation samples. No cross-host before/after timing claim and no relabeling of the historical AMD series."}
        for name, home in HOMES.items():
            proof = WORK / "recovery-validation" / BOOTSTRAPS[name] / "bootstrap.json"
            metadata = json.loads(proof.read_text())
            assert metadata["status"] == "complete" and metadata["source_identity_stable"]
            assert metadata["commit"] == result["source_identities"][name]["commit"]
            assert metadata["tree"] == result["source_identities"][name]["tree"] and not result["source_identities"][name]["git_status"]
            assert all(value == metadata["after"][path] for path, value in result["source_identities"][name]["input_sha256"].items() if path != "Makefile")
            binary = home / "pystachy"
            assert replay.digest(binary) == metadata["artifacts"]["pystachy"]["sha256"]
            result["native_compilers"][name] = {"path": str(binary), "sha256": replay.digest(binary), "bootstrap_record_sha256": replay.digest(proof)}
        probes = out / "probes"
        probes.mkdir()
        for name in ("ordinary_calls", "object_calls", "json_calls", "json_file_calls"):
            shutil.copyfile(HOMES["aaec"] / "bench/recursion" / (name + ".py"), probes / (name + ".py"))
        text = (probes / "json_calls.py").read_text()
        warmed = text.replace('print("warm", kernel(text, n))', 'for warmup in range(4):\n    kernel(text, n)\nprint("warm", kernel(text, n))')
        assert warmed != text
        (probes / "json_warmed.py").write_text(warmed)
        plan = [("ordinary_calls", "ordinary_calls", 10000000, 0), ("object_calls", "object_calls", 100000, 0),
                ("json_calls", "json_calls", 2000, 0), ("json_warmed_short", "json_warmed", 2000, 4),
                ("json_warmed_long", "json_warmed", 20000, 4), ("json_file_calls", "json_file_calls", 20000, 0)]
        for case, source_name, n, warmups in plan:
            source = probes / (source_name + ".py")
            result["cases"][case] = {"source": str(source), "source_sha256": replay.digest(source), "n": n, "extra_untimed_kernel_calls": warmups,
                                      "extra_args": [str(out / "json-input.data")] if case == "json_file_calls" else [], "frontend_ir": {}, "builds": {}, "runs": {}}
    else:
        result = json.loads((out / "measurement.json").read_text())
        assert result["phases"]["prepare"]["status"] == "passed"
    def save():
        replay.save_json(out / "measurement.json", result)
    def verify():
        for name, home in HOMES.items():
            assert replay.source_identity(home)["input_sha256"] == result["source_identities"][name]["input_sha256"]
            assert replay.digest(result["native_compilers"][name]["path"]) == result["native_compilers"][name]["sha256"]
        for case, data in result["cases"].items():
            assert replay.digest(data["source"]) == data["source_sha256"]
            for name, row in data["frontend_ir"].items():
                assert replay.digest(out / (name + "-" + case + ".ll")) == row["sha256"]
            for name, row in data["builds"].items():
                assert replay.digest(out / (name + "-" + case)) == row["sha256"]
    assert args.phase not in result["phases"], "Each phase requires fresh observations; preserve failures before retry"
    harness = {name: replay.digest(ROOT / name) for name in ("measure_recovered.py", "count_support.py", "replay_support.py")}
    phase = {"status": "running", "started_utc": stamp(), "harness_sha256": harness, "load_start": os.getloadavg()}
    result["phases"][args.phase] = phase
    save()
    try:
        verify()
        if args.phase == "prepare":
            warm = out / "warm.py"
            warm.write_text("print(17)\n")
            result["runtime_warmups"] = {}
            for name, home in HOMES.items():
                row = run([result["native_compilers"][name]["path"], "run", warm], home, envs[name])
                assert row["stdout"] == "17\n"
                result["runtime_warmups"][name] = row
            for case, data in result["cases"].items():
                source, n, extra = data["source"], data["n"], data["extra_args"]
                oracle = replay.parse(run([sys.executable, source, n, *extra], out, environment))
                data.update(cpython_oracle=oracle, checksum=oracle["checksum"])
                names = list(HOMES) if case.startswith("json") else ["eca", "aaec"]
                for name in names:
                    home, native = HOMES[name], result["native_compilers"][name]["path"]
                    ir, executable = out / (name + "-" + case + ".ll"), out / (name + "-" + case)
                    row = run([native, "ir", source, "-o", ir], home, envs[name])
                    row.update(sha256=replay.digest(ir), ir_lines=len(ir.read_text().splitlines()))
                    data["frontend_ir"][name] = row
                    hosted = out / (name + "-" + case + "-hosted.ll")
                    run([sys.executable, "-m", "pystachy", "ir", source, "-o", hosted], home, envs[name])
                    assert hosted.read_bytes() == ir.read_bytes(), (name, case, "native/hosted IR mismatch")
                    row["hosted_ir_sha256"] = replay.digest(hosted)
                    row = run([native, "build", source, "-o", executable], home, envs[name])
                    row.update(sha256=replay.digest(executable), binary_bytes=executable.stat().st_size)
                    data["builds"][name] = row
                    for mode, command in (("jit", [native, "run", source, n, *extra]), ("aot", [executable, n, *extra])):
                        data.setdefault("correctness", {}).setdefault(name, {})[mode] = replay.parse(run(command, home, envs[name]), data["checksum"])
                    save()
                result["equivalence"][case] = {kind: {"before_sha256": data[key]["eca"]["sha256"], "after_sha256": data[key]["aaec"]["sha256"],
                                                      "identical": data[key]["eca"]["sha256"] == data[key]["aaec"]["sha256"]}
                                                for kind, key in (("raw_ir", "frontend_ir"), ("aot_binary", "builds"))}
                print("prepared", case, flush=True)
            for relative in ("src/pystachy_compiler/driver.py", "src/pystachy_compiler/specs.py", "src/pystachy_compiler/lower_module.py", "runtime.c"):
                assert replay.digest(HOMES["eca"] / relative) == replay.digest(HOMES["aaec"] / relative)
            layout_values = {path.read_bytes() for path in (out / "aaec-cache").glob("*.target")}
            assert len(layout_values) == 1
            layout = next(iter(layout_values)).decode()
            tree = ast.parse((HOMES["aaec"] / "src/pystachy_compiler/lower_module.py").read_text())
            hooks = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "OBJHOOKS" for t in node.targets))
            # Observe one actual driver execution before accepting reconstructed
            # JIT inputs. This separate correctness capture is never timed.
            capture = out / "driver-proof"
            capture.mkdir()
            wrapper = capture / "llvm"
            wrapper.mkdir()
            wrapper_text = '''#!PYTHON
import hashlib,json,os,sys
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
 record={"arguments":sys.argv[1:],"runtime_fd8_sha256":hashlib.sha256(b"".join(data)).hexdigest(),"runtime_fd8_path":os.readlink("/proc/self/fd/8")}
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
            shutil.copytree(out / "aaec-cache", capture / "cache")
            capture_env = dict(envs["aaec"], PYSTACHY_LLVM=str(wrapper), PYSTACHY_CACHE=str(capture / "cache"), DRIVER_PROOF=str(capture))
            probe = result["cases"]["json_calls"]
            proof_run = replay.parse(run([result["native_compilers"]["aaec"]["path"], "run", probe["source"], probe["n"]], HOMES["aaec"], capture_env), probe["checksum"])
            expected_input = (layout + (out / "aaec-json_calls.ll").read_text() + hooks).encode()
            assert (capture / "actual-input.ll").read_bytes() == expected_input
            actual_lli = json.loads((capture / "lli.json").read_text())
            assert "-dlopen=/dev/fd/8" in actual_lli["arguments"]
            actual_library = Path(actual_lli["runtime_fd8_path"])
            assert actual_library.suffix == ".so" and os.access(actual_library, os.X_OK)
            assert replay.digest(actual_library) == actual_lli["runtime_fd8_sha256"]
            result["actual_driver_proof"] = {"execution": proof_run, "actual_input_sha256": replay.digest(capture / "actual-input.ll"),
                                             "input_exactly_equals_target_raw_hooks": True, "opt_arguments": json.loads((capture / "opt-arguments.json").read_text()),
                                             "lli": actual_lli, "scope": "Separate untimed capture with runtime-cache validation; actual shared-library path verified, not inferred."}
            jit = out / "jit-equivalence"
            jit.mkdir()
            for case in result["cases"]:
                rows = {}
                for name in ("eca", "aaec"):
                    raw = (out / (name + "-" + case + ".ll")).read_text()
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
                    row = run([llvm / "opt", "-passes=" + pipeline, prog, "-o", bc], out, environment)
                    text_path = jit / (name + "-" + case + ".ll")
                    run([llvm / "opt", "-S", "-passes=verify", bc, "-o", text_path], out, environment)
                    row.update(sha256=replay.digest(bc), input_sha256=replay.digest(prog), optimized_text_sha256=replay.digest(text_path), pipeline=pipeline)
                    rows[name] = row
                result["equivalence"][case]["jit_optimized_bitcode"] = {"before_sha256": rows["eca"]["sha256"], "after_sha256": rows["aaec"]["sha256"],
                                                                           "identical": rows["eca"]["sha256"] == rows["aaec"]["sha256"], "records": rows,
                                                                           "scope": "Exact bytes, identical opt input path, correct target and OBJHOOKS; no normalization."}
                result["equivalence"][case]["all_artifacts_identical"] = all(result["equivalence"][case][key]["identical"] for key in ("raw_ir", "aot_binary", "jit_optimized_bitcode"))
                save()
            result["changed_cases"] = [name for name, rows in result["equivalence"].items() if not rows["all_artifacts_identical"]]
            result["unchanged_cases"] = [name for name, rows in result["equivalence"].items() if rows["all_artifacts_identical"]]
            assert all(name.startswith("json") for name in result["changed_cases"]), result["changed_cases"]
            print("changed", result["changed_cases"], flush=True)
        elif args.phase == "counts":
            for name in HOMES:
                shutil.copytree(out / (name + "-cache"), out / (name + "-count-cache"))
            count_support.collect(out, result, HOMES, envs, environment, run, save)
        elif args.phase == "timings":
            names = list(HOMES)
            orders = []
            for index in range(6):
                offset = index % 3
                order = names[offset:] + names[:offset]
                if index // 3:
                    order.reverse()
                orders.append(order)
            assert all([sum(order[position] == name for order in orders) for position in range(3)] == [2, 2, 2] for name in names)
            phase["process_orders"] = orders
            for case in result["changed_cases"]:
                data = result["cases"][case]
                for index, order in enumerate(orders):
                    for mode in ("jit", "aot"):
                        for name in order:
                            command = ([result["native_compilers"][name]["path"], "run", data["source"]] if mode == "jit" else [out / (name + "-" + case)]) + [data["n"], *data["extra_args"]]
                            row = replay.parse(run(command, HOMES[name], envs[name]), data["checksum"])
                            row["round"] = index
                            data["runs"].setdefault(name + "_" + mode, []).append(row)
                            save()
                data["median_ns"] = {name: statistics.median(row["median_ns"] for row in rows) for name, rows in data["runs"].items()}
                data["ratios_to_main"] = {name + "_" + mode: data["median_ns"][name + "_" + mode] / data["median_ns"]["main_" + mode] for name in HOMES for mode in ("jit", "aot")}
                print("timed", case, data["ratios_to_main"], flush=True)
        elif args.phase == "compile":
            names = list(HOMES)
            phase["samples"] = 3
            for case in result["changed_cases"]:
                data = result["cases"][case]
                for index in range(3):
                    for name in names[index:] + names[:index]:
                        for stage, suffix, key in (("ir", ".ll", "frontend_ir"), ("build", "", "builds")):
                            target = out / (name + "-" + case + "-compile" + suffix)
                            row = run([result["native_compilers"][name]["path"], stage, data["source"], "-o", target], HOMES[name], envs[name])
                            row.update(sample=index, sha256=replay.digest(target))
                            assert row["sha256"] == data[key][name]["sha256"]
                            data.setdefault("compile_samples", {}).setdefault(name + "_" + stage, []).append(row)
                            save()
                print("compiled", case, flush=True)
        verify()
        assert harness == {name: replay.digest(ROOT / name) for name in harness}
        phase["status"] = "passed"
    except BaseException as error:
        phase.update(status="failed", error=str(error), failure_record=getattr(error, "record", None))
        raise
    finally:
        phase.update(finished_utc=stamp(), load_end=os.getloadavg())
        save()

if __name__ == "__main__":
    main()
