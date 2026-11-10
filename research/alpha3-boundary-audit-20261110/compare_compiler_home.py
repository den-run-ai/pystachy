"""Run each compiler with its own library under the same relative home spelling."""
import os
from pathlib import Path
import json
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
args = sys.argv[2:]
original = Path.cwd()
env = os.environ.copy()
env["PYSTACHY_HOME"] = "."
if env.get("PYSTACHY_PATH"):
    env["PYSTACHY_PATH"] = os.pathsep.join(
        str((original / item).resolve()) if not Path(item).is_absolute() else item
        for item in env["PYSTACHY_PATH"].split(os.pathsep) if item
    )
if args and args[0] in ("ir", "rt", "check") and len(args) > 1:
    args[1] = str((original / args[1]).resolve())
if "-o" in args:
    index = args.index("-o") + 1
    args[index] = str((original / args[index]).resolve())
os.chdir(root)
result = subprocess.run([sys.executable, "pystachy.py", *args], env=env, check=False)
if "-o" in args:
    output = Path(args[args.index("-o") + 1])
    if output.exists():
        prefix = str(root / "lib").encode() + b"/"
        canonical = str(root.with_name("oracle-ref") / "lib").encode() + b"/"
        assert len(prefix) == len(canonical)
        rows = output.read_bytes().splitlines(keepends=True)
        count = 0
        for i, row in enumerate(rows):
            # Only the previously observed, generated ImportError string constants.
            # Equal-length checkout names keep every LLVM length field unchanged.
            if (row.startswith(b"@s.") and b' c"cannot import name ' in row
                    and b" = private unnamed_addr global " in row
                    and row.count(prefix) == 1):
                rows[i] = row.replace(prefix, canonical)
                count += 1
        if count:
            output.write_bytes(b"".join(rows))
            report = {"root": str(root), "input": args[1], "normalized_import_error_constants": count}
            fd = os.open("/workspace/scratch/313635e688cf/ir-path-normalizations.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(fd, (json.dumps(report) + "\n").encode())
            finally:
                os.close(fd)
sys.exit(result.returncode)
