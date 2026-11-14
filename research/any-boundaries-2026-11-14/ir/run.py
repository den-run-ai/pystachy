"""Run the pinned two-worker audit and verify its inputs before and after."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
TOOLS = Path('/workspace/scratch/c2b093657c17/toolchains/llvm18/payload/usr/lib/llvm-18')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(record):
    home = Path(record["home"])
    assert sha(home / "pystachy") == record["binary_sha256"]
    for name, expected in record["source_files"].items():
        assert sha(home / name) == expected, name
    wanted = set(record["source_files"]) | {"pystachy"}
    actual = {str(p.relative_to(home)) for p in home.rglob("*") if p.is_file()}
    assert actual == wanted, sorted(actual ^ wanted)


records = [json.loads((ROOT / (key + "-identity.json")).read_text()) for key in ("old", "new")]
for record in records:
    verify(record)
oracle = json.loads((ROOT / "oracle.json").read_text())
script = Path(oracle["wrapper"])
assert sha(script) == oracle["wrapper_sha256"]
cases = [c["path"] for c in records[1]["cases"]]
temporary = ROOT / "retained"
temporary.mkdir()
env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_") and k not in ("PYTHONHOME", "PYTHONPATH")}
env.update(PYSTACHY_JOBS="2", PYSTACHY_CASE_TIMES=str(ROOT / "times.txt"),
           PYSTACHY_LLVM=str(TOOLS / "bin"), LD_LIBRARY_PATH=str(TOOLS / "lib"),
           TMPDIR=str(temporary), LC_ALL="C")
command = ["sh", str(script), *[str(Path(r["home"]) / "pystachy") for r in records], *cases]
(ROOT / "command.json").write_text(json.dumps({"command": command,
    "overrides": {k: v for k, v in env.items() if k.startswith("PYSTACHY_") or k in ("TMPDIR", "LC_ALL", "LD_LIBRARY_PATH")},
    "cleared": "All inherited PYSTACHY_* plus PYTHONHOME and PYTHONPATH"}, indent=2) + "\n")
with (ROOT / "raw.log").open("x") as out:
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=out, stderr=subprocess.STDOUT)
(ROOT / "raw.status").write_text(str(result.returncode) + "\n")
for record in records:
    verify(record)
(ROOT / "source-rechecked.json").write_text(json.dumps({"before_and_after_inputs_identical": True,
    "old_identity_sha256": sha(ROOT / "old-identity.json"), "new_identity_sha256": sha(ROOT / "new-identity.json"),
    "raw_exit": result.returncode}, indent=2) + "\n")
print("Raw audit exit:", result.returncode)
print((ROOT / "raw.log").read_text()[-2000:])
