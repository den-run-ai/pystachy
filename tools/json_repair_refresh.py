"""Prepare reproducible repair, schema and CPython-companion benchmark configs.

Build the probes/companion first. This tool writes configs, never builds or times
them. Run each config with json_repair_bench.py on an otherwise quiet host.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from json_repair_bench import digest, validate_config


ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_COMMIT = "36d7a6ed53e777b5a5b9017e33d35ea2af8b7c6e"
PROBES = ROOT / "bench/json_repair"
MANIFEST = ROOT / "tests/upstream/json_repair/manifest.json"
SCHEMA_MODES = (
    "validate-valid", "validate-early", "validate-late", "is-valid-mixed",
    "check-schema", "repair-standard", "repair-salvage", "repair-error",
)
DEPENDENCIES = ("jsonschema", "attrs", "referencing", "rpds-py", "jsonschema-specifications", "typing_extensions")


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def upstream_identity(upstream):
    """Reject wrong, modified or incomplete upstream packages before config output."""
    manifest = json.loads(MANIFEST.read_text())
    commit = git(upstream, "rev-parse", "HEAD")
    if manifest["commit"] != UPSTREAM_COMMIT or commit != UPSTREAM_COMMIT:
        raise ValueError("upstream must be pristine json_repair 0.64.9 at the pinned manifest commit")
    if git(upstream, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("upstream checkout must be clean, including untracked files")
    expected = manifest["source_sha256"]
    actual_paths = {str(path.relative_to(upstream)) for path in (upstream / "src/json_repair").rglob("*.py")}
    if actual_paths != set(expected):
        raise ValueError("upstream Python source inventory differs from the manifest")
    hashes = {str(upstream / name): digest(upstream / name) for name in expected}
    if any(hashes[str(upstream / name)] != value for name, value in expected.items()):
        raise ValueError("upstream source hashes differ from the pinned manifest")
    return {"commit": commit, "tag": manifest["tag"], "source_sha256": hashes}


def python_identity(python):
    script = '''import importlib.metadata as metadata
import json, pathlib, platform, sys
packages = {}
for name in json.loads(sys.argv[1]):
    dist = metadata.distribution(name)
    files = []
    for entry in dist.files or []:
        path = pathlib.Path(dist.locate_file(entry)).resolve()
        if path.is_file() and path.suffix != ".pyc" and "__pycache__" not in path.parts:
            files.append(str(path))
    packages[name] = {"version": dist.version, "files": sorted(files)}
print(json.dumps({"executable": sys.executable, "version": platform.python_version(),
                  "sys_version": sys.version, "packages": packages}))
'''
    identity = json.loads(subprocess.check_output(
        [str(python), "-I", "-c", script, json.dumps(DEPENDENCIES)], text=True
    ))
    pinned_python = (ROOT / ".python-version").read_text().strip()
    if identity["version"] != pinned_python:
        raise ValueError(f"oracle Python must be {pinned_python}, got {identity['version']}")
    if identity["packages"]["jsonschema"]["version"] != "4.26.0":
        raise ValueError("oracle jsonschema must be 4.26.0")
    files = {file for package in identity["packages"].values() for file in package.pop("files")}
    return identity, {file: digest(file) for file in sorted(files)}


def file_hashes(paths):
    result = {}
    for path in paths:
        path = Path(path).resolve()
        if not path.is_file():
            raise ValueError(f"benchmark input does not exist: {path}")
        result[str(path)] = digest(path)
    return result


def llvm_identity(directory):
    commands = {}
    hashes = {}
    for name in ("clang", "llvm-link", "opt", "llc", "lli"):
        path = (Path(directory) / name).resolve()
        hashes.update(file_hashes([path]))
        version = subprocess.check_output([str(path), "--version"], text=True).splitlines()[0]
        commands[name] = {"path": str(path), "version": version, "sha256": hashes[str(path)]}
    library = llvm_shared_library(commands["lli"]["path"])
    commands["lli"]["shared_library"] = library
    # Keep the mapped name too: a changed symlink must not retain the old target's identity.
    hashes[library["path"]] = library["sha256"]
    hashes[library["realpath"]] = library["sha256"]
    return commands, hashes


def llvm_shared_library(lli):
    """Select the libLLVM mapping of this lli in the measured loader environment."""
    ldd = shutil.which("ldd")
    if ldd is None:
        raise ValueError("ldd is required to identify the selected lli's libLLVM")
    result = subprocess.run([ldd, lli], env=dict(os.environ), text=True,
                            capture_output=True, timeout=10, check=False)
    lines = [line for line in result.stdout.splitlines() if line.lstrip().startswith("libLLVM")]
    if result.returncode or len(lines) != 1:
        raise ValueError("expected exactly one resolved libLLVM mapping from ldd lli")
    match = re.fullmatch(r"\s*libLLVM\S*\s+=>\s+(.+?)\s+\(0x[0-9a-fA-F]+\)\s*", lines[0])
    if match is None:
        raise ValueError("lli's libLLVM mapping is unresolved or malformed")
    mapped = Path(match.group(1))
    if not mapped.is_absolute() or not mapped.is_file():
        raise ValueError("lli's libLLVM mapping must name an existing absolute file")
    return {"path": str(mapped), "realpath": str(mapped.resolve()), "sha256": digest(mapped)}


def make_configs(*, upstream, python, native_dir, companion_dir):
    upstream = Path(upstream).resolve()
    python = Path(python).absolute()
    native_dir = Path(native_dir).resolve()
    companion_dir = Path(companion_dir).resolve()
    llvm = os.environ.get("PYSTACHY_LLVM", "")
    ld_library_path = os.environ.get("LD_LIBRARY_PATH", "")
    if not llvm or not ld_library_path:
        raise ValueError("set PYSTACHY_LLVM and LD_LIBRARY_PATH to the native build's toolchain")
    upstream_info = upstream_identity(upstream)
    python_info, dependency_hashes = python_identity(python)
    llvm_info, llvm_hashes = llvm_identity(llvm)
    common_hashes = file_hashes([
        MANIFEST, ROOT / "tools/json_repair_bench.py", Path(__file__), ROOT / "lljit.c",
        *PROBES.glob("*.py"), *PROBES.glob("*.json"),
    ])
    binaries = {name: native_dir / name for name in ("bench", "facade", "scaling", "schema")}
    file_hashes(binaries.values())
    native_package = companion_dir / "pystachy_json_repair"
    extensions = list(native_package.glob("_native*.so"))
    if len(extensions) != 1:
        raise ValueError("companion directory must contain exactly one compiled _native extension")
    companion_hashes = file_hashes([native_package / "__init__.py", extensions[0], ROOT / "pyext.c"])
    provided = {"python": python_info, "upstream": upstream_info,
                "llvm_tools": llvm_info,
                "common_probe_sha256": common_hashes,
                "timing_scope": "steady repeated API calls; setup and complete-result validation excluded"}
    jit_env = {"PYSTACHY_HOME": str(ROOT), "PYSTACHY_PATH": str(ROOT / "ports"),
               "PYSTACHY_LLVM": llvm, "LD_LIBRARY_PATH": ld_library_path,
               "PYSTACHY_CACHE": str(native_dir / "jit-cache")}
    native_env = {"LD_LIBRARY_PATH": ld_library_path}
    upstream_env = {"PYTHONPATH": str(upstream / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
    adapted_env = {"PYTHONPATH": str(ROOT / "ports"), "PYTHONDONTWRITEBYTECODE": "1"}
    variants = []
    for name, source, env, inputs in (
        ("upstream-cpython", upstream, upstream_env,
         common_hashes | dependency_hashes | upstream_info["source_sha256"]),
        ("adapted-cpython", ROOT, adapted_env, common_hashes | dependency_hashes),
        ("port-aot", ROOT, native_env, common_hashes),
        ("port-jit", ROOT, jit_env, common_hashes | llvm_hashes),
    ):
        commands = {}
        for probe in binaries:
            script = PROBES / ("schema_upstream.py" if probe == "schema" and name == "upstream-cpython" else probe + ".py")
            if name == "port-aot":
                command = [str(binaries[probe])]
            elif name == "port-jit":
                command = [str(ROOT / "pystachy"), "run", str(script)]
            else:
                command = [str(python), str(script)]
            commands[probe] = command
        variants.append({"name": name, "source": str(source), "commands": commands,
                         "env": env, "input_sha256": inputs, "identity": copy.deepcopy(provided)})
    repair_cases = [
        {"name": "mixed-records", "probe": "bench", "args": ["1000"], "calls_per_round": 10},
        {"name": "malformed-objects", "probe": "facade", "args": ["malformed", "1500"], "calls_per_round": 4},
        {"name": "serialized-malformed", "probe": "facade", "args": ["serialized-malformed", "1500"], "calls_per_round": 4},
        {"name": "valid-objects", "probe": "facade", "args": ["valid", "10000"], "calls_per_round": 4},
        {"name": "unicode-malformed", "probe": "scaling", "args": ["unicode", "2000", "200"], "calls_per_round": 1},
        {"name": "escaped-newlines", "probe": "scaling", "args": ["escaped", "2000", "50"], "calls_per_round": 1},
        {"name": "logged-repair", "probe": "scaling", "args": ["logs", "1000", "1000"], "calls_per_round": 1},
    ]
    schema_rounds = {"validate-valid": 200, "validate-early": 3000, "validate-late": 200,
                     "is-valid-mixed": 500, "check-schema": 10,
                     "repair-standard": 100, "repair-salvage": 100, "repair-error": 100}
    schema_cases = [{"name": mode, "probe": "schema", "args": [mode, str(schema_rounds[mode])],
                     "calls_per_round": 4} for mode in SCHEMA_MODES]
    repair_variants = copy.deepcopy(variants)
    for variant in repair_variants:
        variant["commands"].pop("schema")
    schema_variants = copy.deepcopy(variants)
    for variant in schema_variants:
        variant["commands"] = {"schema": variant["commands"]["schema"]}
    companion_variants = []
    for name, module, source, env, extra in (
        ("upstream-cpython", "json_repair", upstream, upstream_env, upstream_info["source_sha256"]),
        ("native-companion", "pystachy_json_repair", ROOT,
         {"PYTHONPATH": str(companion_dir), "PYTHONDONTWRITEBYTECODE": "1", **native_env}, companion_hashes),
    ):
        companion_variants.append({
            "name": name, "source": str(source), "env": env,
            "commands": {"companion": [str(python), str(PROBES / "companion.py"), module,
                                       "--cases", str(PROBES / "companion_cases.json")]},
            "input_sha256": common_hashes | dependency_hashes | extra,
            "identity": copy.deepcopy(provided),
        })
    companion_cases = [
        {"name": f"{api}-{mix}", "probe": "companion", "args": [api, mix, "1000"],
         "calls_per_round": 20 if mix == "mixed" else 4}
        for api in ("text", "objects", "logs") for mix in ("mixed", "malformed")
    ]
    configs = {"repair": {"variants": repair_variants, "cases": repair_cases},
               "schema": {"variants": schema_variants, "cases": schema_cases},
               "companion": {"variants": companion_variants, "cases": companion_cases}}
    for config in configs.values():
        validate_config(config)
    return configs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--native-dir", type=Path, default=ROOT / "build/json-refresh")
    parser.add_argument("--companion-dir", type=Path, default=ROOT / "build/json-refresh")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    configs = make_configs(upstream=args.upstream, python=args.python,
                           native_dir=args.native_dir, companion_dir=args.companion_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, config in configs.items():
        path = args.output_dir / f"{name}.json"
        path.write_text(json.dumps(config, indent=2) + "\n")
        print(path)


if __name__ == "__main__":
    main()
