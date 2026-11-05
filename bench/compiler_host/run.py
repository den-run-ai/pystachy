"""Compare compiler hosts on identical frozen inputs and exact emitted bytes.

Run from the repository root. A config contains hosts (name, command), inputs
(name, path, mode=ir, optional import_path), and optional environment values.
Commands are argv lists, never shell strings. Preparation is deliberately separate.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import statistics
import sys


ROOT = Path(__file__).resolve().parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


measure = load_module("compiler_parallel_measure", ROOT / "bench/compiler_parallel/llvm_partitions.py")
bootstrap = load_module("bootstrap_identity", ROOT / "tools/bootstrap_pipeline.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temp.replace(path)


def host_artifacts(hosts):
    files = {}
    for host in hosts:
        if not host.get("artifact_root"):
            continue
        root = Path(host["artifact_root"])
        paths = [root / "pystachy.py", *root.glob("*.so")]
        paths += [p for p in (root / "src").rglob("*") if p.suffix in (".py", ".so")]
        files[host["name"]] = {str(p.resolve()): sha(p) for p in sorted(paths)}
    return files


def inspect_hosts(hosts, env, timeout):
    reports = {}
    probe = ("import sys,json;sys.path.insert(0,sys.argv[1]);import pystachy;"
             "print(json.dumps({'python':sys.version,'modules':{k:v.__file__ for k,v in sys.modules.items() "
             "if k=='src' or k.startswith('src.')}}))")
    for host in hosts:
        if not host.get("artifact_root"):
            continue
        result = measure.execute([host["command"][0], "-c", probe, host["artifact_root"]], env, timeout)
        measure.successful(result)
        info = json.loads(result["stdout"])
        root = Path(host["artifact_root"]).resolve()
        modules = info["modules"]
        expected_count = len(list((root / "src").rglob("*.py")))
        if len(modules) != expected_count or any(not Path(p).resolve().is_relative_to(root) for p in modules.values()):
            raise RuntimeError(f"unexpected host import inventory for {host['name']}")
        expected = ".so" if host.get("compiled") else ".py"
        if any(not p.endswith(expected) for p in modules.values()):
            raise RuntimeError(f"host {host['name']} silently fell back or loaded compiled modules")
        reports[host["name"]] = info
    return reports


def input_artifacts(inputs):
    paths = set()
    for item in inputs:
        source = Path(item["path"]).resolve()
        paths.add(source)
        paths.update(source.parent.glob("*.py"))
        for directory in item.get("import_path", "").split(":"):
            if directory:
                paths.update(Path(directory).resolve().rglob("*.py"))
    return {str(p): sha(p) for p in sorted(paths)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--cpu", type=int)
    args = parser.parse_args()
    if args.samples < 1 or args.timeout <= 0:
        parser.error("samples and timeout must be positive")
    args.work = args.work.resolve()
    args.work.mkdir(parents=True, exist_ok=False)
    config = json.loads(args.config.read_text())
    hosts, inputs = config["hosts"], config["inputs"]
    if (not hosts or not inputs or len({h["name"] for h in hosts}) != len(hosts)
            or len({item["name"] for item in inputs}) != len(inputs)):
        parser.error("need unique nonempty hosts and inputs")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env.update({"PYSTACHY_HOME": str(ROOT), "PYSTACHY_TIMING": "1", "PYTHONHASHSEED": "0"})
    env.update(config.get("environment", {}))
    source = bootstrap.source_identity(ROOT)
    artifacts = host_artifacts(hosts)
    imported_inputs = input_artifacts(inputs)
    commands = {h["name"]: h["command"] for h in hosts}
    fingerprints = {str(Path(p).resolve()): sha(p) for h in hosts for p in h["command"]
                    if Path(p).is_file()}
    report = {"config": config, "environment": {k: env[k] for k in env
              if k.startswith("PYSTACHY_") or k in ("PYTHONHASHSEED", "LD_LIBRARY_PATH")},
              "source": source, "host_state": bootstrap.host_state(),
              "host_artifacts": artifacts, "host_imports": inspect_hosts(hosts, env, args.timeout),
              "input_artifacts": imported_inputs,
              "command_fingerprints": fingerprints, "samples": [], "oracles": {},
              "requested_samples": args.samples, "cpu": args.cpu, "complete": False}
    rng = random.Random(20261105)
    for item in inputs:
        path = str(Path(item["path"]).resolve())
        input_env = env | {"PYSTACHY_PATH": item.get("import_path", "")}
        oracle = None
        # The first host supplies a fresh-process oracle before interleaved timings.
        schedule = [("oracle", hosts[0])]
        for sample in range(args.samples):
            order = hosts.copy()
            rng.shuffle(order)
            schedule.extend((sample, host) for host in order)
        for sample, host in schedule:
            output = args.work / f"{item['name']}-{host['name']}-{sample}.ll"
            command = commands[host["name"]] + [item.get("mode", "ir"), path, "-o", str(output)]
            if args.cpu is not None:
                command = ["taskset", "-c", str(args.cpu)] + command
            result = measure.execute(command, input_env, args.timeout)
            result.update({"host": host["name"], "input": item["name"], "sample": sample,
                           "input_sha256": sha(path)})
            result["output_sha256"] = sha(output) if output.is_file() else None
            result["output_bytes"] = output.stat().st_size if output.is_file() else None
            result["stages"] = [dict(zip(("stage", "seconds"), (line.split("\t")[1],
                                  float(line.split("\t")[2]))))
                                for line in result["stderr"].splitlines()
                                if line.startswith("pystachy-timing\t")]
            if sample == "oracle":
                report["oracles"][item["name"]] = result
                atomic_json(args.report, report)
                measure.successful(result)
                if result["output_sha256"] is None:
                    raise RuntimeError("oracle produced no output")
                oracle = result["output_sha256"]
                report["oracles"][item["name"]] = result
            else:
                result["matches_oracle"] = (result["exit_code"] == 0 and not result["timed_out"]
                                             and result["output_sha256"] == oracle)
                report["samples"].append(result)
                print(f"{item['name']} {host['name']} {sample}: {result['wall_s']:.4f}s "
                      f"match={result['matches_oracle']}", flush=True)
            atomic_json(args.report, report)
    report["source_unchanged"] = source == bootstrap.source_identity(ROOT)
    report["commands_unchanged"] = fingerprints == {p: sha(p) for p in fingerprints}
    report["host_artifacts_unchanged"] = artifacts == host_artifacts(hosts)
    report["input_artifacts_unchanged"] = imported_inputs == input_artifacts(inputs)
    report["summary"] = []
    for item in inputs:
        for host in hosts:
            rows = [r for r in report["samples"] if r["input"] == item["name"] and r["host"] == host["name"]]
            good = all(r["matches_oracle"] for r in rows)
            summary = {"input": item["name"], "host": host["name"], "n": len(rows), "correct": good}
            if good:
                for key in ("wall_s", "cpu_s", "wait4_max_process_rss_kib", "sampled_process_tree_peak_rss_kib"):
                    values = [r[key] for r in rows if r[key] is not None]
                    summary[key] = {"median": statistics.median(values), "min": min(values), "max": max(values)} if values else None
            report["summary"].append(summary)
    report["complete"] = (report["source_unchanged"] and report["commands_unchanged"]
                          and report["host_artifacts_unchanged"]
                          and report["input_artifacts_unchanged"]
                          and all(r["matches_oracle"] for r in report["samples"]))
    atomic_json(args.report, report)
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
