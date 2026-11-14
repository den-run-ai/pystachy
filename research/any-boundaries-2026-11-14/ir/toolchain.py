"""Record executable versions and hashes used by the native IR audit harness."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
LLVM = Path("/workspace/scratch/c2b093657c17/toolchains/llvm18/payload/usr/lib/llvm-18")
paths = {"harness_python": Path(sys.executable), "shell": Path("/bin/sh")}
for name in ("sha256sum", "cmp", "diff", "sed", "date", "xz"):
    paths[name] = Path("/usr/bin") / name
for name in ("clang", "llc", "llvm-as", "llvm-config"):
    paths[name] = LLVM / "bin" / name
result = {"platform": platform.platform(), "uname": list(platform.uname()), "python": sys.version,
          "pinned_llvm_directory": str(LLVM / "bin"), "native_ir_only": True, "tools": {}}
env = os.environ.copy()
env["LD_LIBRARY_PATH"] = str(LLVM / "lib")
for name, path in paths.items():
    command = [str(path), "--version"] if name != "shell" else [str(path), "-c", 'printf "%s\\n" "$0"']
    output = subprocess.run(command, capture_output=True, text=True, env=env)
    result["tools"][name] = {"path": str(path), "resolved_path": str(path.resolve()),
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                             "version_returncode": output.returncode, "version": (output.stdout + output.stderr).strip()}
for side in ("old", "new"):
    path = ROOT / ("home-" + side) / "pystachy"
    output = subprocess.run(["ldd", str(path)], capture_output=True, text=True, env=env)
    result[side + "_compiler_dependencies"] = {"command": ["ldd", str(path)], "exit": output.returncode,
                                                "output": output.stdout + output.stderr}
(ROOT / "toolchain.json").write_text(json.dumps(result, indent=2) + "\n")
