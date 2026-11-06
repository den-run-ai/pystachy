"""Build application GC variants and verify them against CPython before timing.

The spec supplies source_root, oracle_python, cases and variants. Cases have
name/source/args/smoke_args and optional python_path/inputs. Variants have
name/compiler/home/build_env/run_env and optional build_inputs; build_from reuses an earlier executable.
Spec build_env/run_env provide common settings; native GC pacing belongs in
native variants. Paths are relative to the spec, except case paths (source_root).
Use a fresh output directory. Generated configs run with ../gc_locality/run.py.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean_environment(extra):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("PYSTACHY_", "GC_"))
           and k not in ("LD_PRELOAD", "PYTHONPATH", "PYTHONHOME")}
    env.update(extra)
    return env


def git_identity(path):
    def query(*args):
        p = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True)
        return p.stdout.strip() if p.returncode == 0 else None
    return {"revision": query("rev-parse", "HEAD"), "tree": query("rev-parse", "HEAD^{tree}"),
            "status": query("status", "--porcelain", "--untracked-files=all")}


def fingerprint(paths):
    """Hash explicit files and Python/C/header trees, following directory links once."""
    files, visited = {}, set()
    for path in map(Path, paths):
        if path.is_file():
            files[str(path.resolve())] = digest(path)
        elif path.is_dir():
            for folder, dirs, names in os.walk(path, followlinks=True):
                real = Path(folder).resolve()
                if real in visited:
                    dirs[:] = []
                    continue
                visited.add(real)
                for name in names:
                    file = Path(folder, name)
                    if file.suffix in (".py", ".c", ".h"):
                        files[str(file.resolve())] = digest(file)
        else:
            raise FileNotFoundError(path)
    return dict(sorted(files.items()))


def validate(spec, base, root):
    cases, variants = spec["cases"], spec["variants"]
    for rows in (cases, variants):
        names = [row["name"] for row in rows]
        if not names or len(set(names)) != len(names) or any(
            not isinstance(n, str) or not n or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in n)
            for n in names
        ):
            raise ValueError("case and variant names must be unique lowercase path-safe names")
    seen = set()
    for variant in variants:
        if "build_from" in variant:
            if variant["build_from"] not in seen or any(k in variant for k in ("compiler", "home", "build_env", "build_inputs")):
                raise ValueError("build_from must name an earlier variant and cannot supply build settings")
        elif not ((base / variant["compiler"]).is_file() and (base / variant["home"] / "runtime.c").is_file()):
            raise ValueError("variant compiler and home/runtime.c must exist")
        inputs = variant.get("build_inputs", [])
        if not isinstance(inputs, list) or not all(isinstance(p, str) and (base / p).exists() for p in inputs):
            raise ValueError("build_inputs must list existing files or source/header directories")
        seen.add(variant["name"])
    for row in [spec, *variants]:
        for field in ("build_env", "run_env"):
            env = row.get(field, {})
            if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
                raise ValueError(f"{field} must map strings to strings")
    for case in cases:
        if not (root / case["source"]).is_file():
            raise ValueError("case source must exist")
        for field in ("args", "smoke_args", "python_path", "inputs"):
            if not isinstance(case.get(field, []), list) or not all(isinstance(v, str) for v in case.get(field, [])):
                raise ValueError(f"case {field} must be a list of strings")
        if any(not (root / p).exists() for p in case.get("python_path", []) + case.get("inputs", [])):
            raise ValueError("case import paths and explicit inputs must exist")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("timeout must be positive")
    spec_path = args.spec.resolve()
    spec = json.loads(spec_path.read_text())
    root = (spec_path.parent / spec["source_root"]).resolve()
    python = (spec_path.parent / spec["oracle_python"]).resolve()
    validate(spec, spec_path.parent, root)
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error("use a fresh empty output directory")
    report = {"spec": spec, "spec_sha256": digest(spec_path), "source_root": str(root),
              "source_checkout": git_identity(root), "oracle_python": str(python),
              "oracle_python_sha256": digest(python), "source_manifests": {},
              "oracle_version": subprocess.check_output([str(python), "--version"], text=True).strip(),
              "cases": [], "builds": [], "complete": False}
    out.mkdir(parents=True, exist_ok=True)

    def save():
        (out / "builds.json").write_text(json.dumps(report, indent=2) + "\n")

    def pin(key, paths):
        if key not in report["source_manifests"]:
            report["source_manifests"][key] = {"paths": [str(p) for p in paths], "files_sha256": fingerprint(paths)}
        return key

    def frozen(keys):
        for key in keys:
            manifest = report["source_manifests"][key]
            if fingerprint(manifest["paths"]) != manifest["files_sha256"]:
                raise RuntimeError(f"source or compiler changed during preparation: {key}")

    def run(command, env, label):
        artifact = out / (label + ".artifact")
        artifact.unlink(missing_ok=True)
        has_artifact = any("{output}" in arg for arg in command)
        command = [arg.replace("{output}", str(artifact)) for arg in command]
        result = subprocess.run(command, cwd=root, env=env, capture_output=True, timeout=args.timeout)
        (out / (label + ".stderr")).write_bytes(result.stderr)
        if result.returncode:
            raise RuntimeError(f"{label}: exit {result.returncode}; see {out / (label + '.stderr')}")
        if has_artifact and not artifact.is_file():
            raise RuntimeError(f"{label}: expected output artifact is missing")
        return result.stdout, digest(artifact) if has_artifact else None

    try:
        plans = {}
        for variant in spec["variants"]:
            if "build_from" not in variant:
                home = (spec_path.parent / variant["home"]).resolve()
                compiler = (spec_path.parent / variant["compiler"]).resolve()
                paths = [p for p in home.iterdir() if p.is_file() and p.suffix in (".py", ".c", ".h")]
                paths += [home / p for p in ("src", "lib", "ryu", "mpz") if (home / p).is_dir()]
                keys = [pin("home:" + str(home), paths), pin("compiler:" + str(compiler), [compiler])]
                for p in variant.get("build_inputs", []):
                    path = (spec_path.parent / p).resolve()
                    keys.append(pin("dependency:" + str(path), [path]))
                plans[variant["name"]] = home, compiler, keys
        for case in spec["cases"]:
            name, source = case["name"], root / case["source"]
            input_paths = {source.resolve()}
            for arg in case["args"] + case["smoke_args"] + case.get("inputs", []):
                path = root / arg
                if "{output}" not in arg and path.is_file():
                    input_paths.add(path.resolve())
            imports = {source.parent, *(root / p for p in case.get("python_path", [])),
                       *(root / p for p in case.get("inputs", []) if (root / p).is_dir())}
            keys = [pin("imports:" + str(p), [p]) for p in sorted(imports)]
            keys.append(pin("case:" + name, sorted(input_paths)))
            cp_env = clean_environment({})
            if case.get("python_path"):
                cp_env["PYTHONPATH"] = os.pathsep.join(str(root / p) for p in case["python_path"])
            oracle = {}
            for phase, argv in (("smoke", case["smoke_args"]), ("full", case["args"])):
                frozen(keys)
                print("ORACLE", name, phase, flush=True)
                oracle[phase] = run([str(python), str(source), *argv], cp_env, name + "-oracle-" + phase)
                frozen(keys)
                (out / (name + "-oracle-" + phase + ".stdout")).write_bytes(oracle[phase][0])
            report["cases"].append(dict(case, source_manifest_keys=keys,
                oracle_sha256={k: {"stdout": hashlib.sha256(v[0]).hexdigest(), "artifact": v[1]}
                               for k, v in oracle.items()}))
            built = {}
            config = {"name": name, "cwd": str(root),
                      "inputs": [str(p) for p in sorted(input_paths)] + [str(out / "builds.json")],
                      "address_space_mib": spec.get("address_space_mib", 2048),
                      "env": dict({"PYSTACHY_GC": "stats"}, **spec.get("run_env", {})),
                      "notes": spec.get("notes", ""), "variants": []}
            for variant in spec["variants"]:
                label = variant["name"]
                if "build_from" in variant:
                    executable, executable_hash, build_keys = built[variant["build_from"]]
                else:
                    home, compiler, planned_keys = plans[label]
                    build_keys = list(planned_keys)
                    executable = out / (label + "-" + name)
                    executable.unlink(missing_ok=True)
                    extra = dict(spec.get("build_env", {}), **variant.get("build_env", {}))
                    extra.update(PYSTACHY_HOME=str(home), PYSTACHY_CACHE=str(out / ("cache-" + label)))
                    if case.get("python_path"):
                        extra["PYSTACHY_PATH"] = os.pathsep.join(str(root / p) for p in case["python_path"])
                    for entry in filter(None, extra.get("PYSTACHY_PATH", "").split(os.pathsep)):
                        path = (root / entry).resolve()
                        build_keys.append(pin("imports:" + str(path), [path]))
                    frozen(keys + build_keys)
                    command = [str(compiler), "build", str(source), "-o", str(executable)]
                    print("BUILD", label, name, flush=True)
                    run(command, clean_environment(extra), label + "-" + name + "-build")
                    frozen(keys + build_keys)
                    executable_hash = digest(executable)
                    report["builds"].append({"name": label, "case": name, "argv": command, "env": extra,
                        "home_checkout": git_identity(home), "source_manifest_keys": build_keys,
                        "executable": str(executable), "executable_sha256": executable_hash})
                built[label] = executable, executable_hash, build_keys
                runtime_env = dict(config["env"], **variant.get("run_env", {}))
                for phase, argv, stress in (("smoke", case["smoke_args"], False),
                                           ("smoke", case["smoke_args"], True), ("full", case["args"], False)):
                    frozen(keys + build_keys)
                    if digest(executable) != executable_hash:
                        raise RuntimeError("validated executable changed")
                    env = clean_environment(runtime_env)
                    if stress:
                        env["PYSTACHY_GC_STRESS"] = "1"
                    actual = run([str(executable), *argv], env,
                                 label + "-" + name + "-" + phase + ("-stress" if stress else ""))
                    frozen(keys + build_keys)
                    if actual != oracle[phase] or digest(executable) != executable_hash:
                        (out / (label + "-" + name + "-mismatch.stdout")).write_bytes(actual[0])
                        raise RuntimeError(f"{label}/{name}/{phase}: differs from CPython or executable changed")
                print("PASS", label, name, "smoke, stress, full oracle", flush=True)
                config["variants"].append({"name": label, "argv": [str(executable), *case["args"]],
                                           "env": runtime_env, "validated_executable_sha256": executable_hash})
                save()
            (out / (name + ".json")).write_text(json.dumps(config, indent=2) + "\n")
        report["complete"] = True
    finally:
        save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
