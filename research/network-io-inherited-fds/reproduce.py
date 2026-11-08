"""Record inherited pipe contents under CPython, native AOT and hosted JIT.

Research evidence only. A JIT result different from 50495045 demonstrates the
descriptor-clobber bug; this script does not label that result a passing test.
Run from any cwd with pinned CPython and PYSTACHY_LLVM pointing to LLVM 18.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROBE = HERE / "probe.py"


def main():
    rows = []
    with tempfile.TemporaryDirectory(prefix="pystachy-inherited-fds-") as temporary:
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("PYSTACHY_") or key == "PYSTACHY_LLVM"}
        env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_CACHE=temporary, PYSTACHY_PROGRAM_CACHE="0")
        executable = Path(temporary) / "probe"
        subprocess.run([sys.executable, "pystachy.py", "build", str(PROBE), "-o", str(executable)],
                       cwd=ROOT, env=env, check=True, timeout=120)
        for descriptor in (8, 9, 64):
            for name, command in [("cpython", [sys.executable, str(PROBE)]),
                                  ("aot", [str(executable)]),
                                  ("hosted_jit", [sys.executable, "pystachy.py", "run", str(PROBE)])]:
                reader, writer = os.pipe()
                try:
                    os.write(writer, b"PIPE")
                    os.close(writer)
                    writer = -1
                    os.dup2(reader, descriptor, inheritable=True)
                    result = subprocess.run(command + [str(descriptor)], cwd=ROOT, env=env,
                                            pass_fds=(descriptor,), capture_output=True, timeout=120)
                    rows.append({"fd": descriptor, "mode": name, "stdout": result.stdout.decode(),
                                 "stderr": result.stderr.decode(), "returncode": result.returncode})
                finally:
                    for fd in {reader, writer, descriptor}:
                        if fd >= 0:
                            os.close(fd)
    print(json.dumps({"expected_stdout": "50495045\n", "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
