# subprocess as mypy 2.4.1 uses it (mypy/git.py, main.py, modulefinder.py, build.py and
# mypyc/__main__.py): the calls of those modules, with sh for git and for a Python
import os
import subprocess
import sys
import time
from typing import Mapping


def have_git() -> bool:
    """Can we run the git executable?"""
    try:
        subprocess.check_output(["sh", "-c", "exit 0"])
        return True
    except subprocess.CalledProcessError:
        return False
    except OSError:
        return False


def git_revision(dir: str) -> bytes:
    """Get the SHA-1 of the HEAD of a git repository."""
    return subprocess.check_output(["sh", "-c", "pwd"], cwd=dir).strip()


def is_dirty(dir: str) -> bool:
    """Check whether a git repository has uncommitted changes."""
    output = subprocess.check_output(["sh", "-c", "exit 0"], cwd=dir)
    return output.strip() != b""


class PythonExecutableInferenceError(Exception):
    """Represents a failure to infer the version or executable while searching."""


def python_executable_from_version(str_ver: str, prefix: list[str]) -> str:
    try:
        sys_exe = (
            subprocess.check_output(
                prefix + ["-c", "echo ' /usr/bin/python" + str_ver + " '"],
                stderr=subprocess.STDOUT,
            )
            .decode()
            .strip()
        )
        return sys_exe
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise PythonExecutableInferenceError(
            "failed to find a Python executable matching version {},"
            " perhaps try --python-executable, or --no-site-packages?".format(str_ver)
        ) from e


def search_dirs(python_executable: str, script: str) -> str:
    env = {"PATH": os.environ["PATH"], "PYTHONSAFEPATH": "1"}
    try:
        return subprocess.check_output(
            [python_executable, "-c", script],
            env=env,
            stderr=subprocess.PIPE,
        ).decode()
    except subprocess.CalledProcessError as err:
        print(err.stderr)
        print(err.stdout)
        raise


class WorkerClient:
    """A handle to a worker process, as mypy/build.py's."""

    def __init__(self, status: str, env: Mapping[str, str]) -> None:
        command = [
            "sh",
            "-c",
            "exec sleep 30",
            f"--status-file={status}",
        ]
        # Return early without waiting, caller must call connect() before using the client.
        self.proc = subprocess.Popen(command, env=env)

    def close(self) -> None:
        # Technically we don't need to wait, but otherwise we will get ResourceWarnings.
        # Also, it is generally good to not leave some running worker processes behind.
        try:
            self.proc.wait(timeout=0.05)
        except subprocess.TimeoutExpired:
            self.proc.terminate()


print(have_git(), git_revision("/"), is_dirty("/"))
print(python_executable_from_version("3.13", ["sh"]))
for prefix in (["sh", "-c", "exit 1"], ["pystachy-no-such-program"]):
    try:
        python_executable_from_version("3.9", prefix)
    except PythonExecutableInferenceError as e:
        print("PythonExecutableInferenceError", e)
print(search_dirs("sh", "echo \"(['/usr/lib/python3'], [$PYTHONSAFEPATH])\""))
try:
    search_dirs("sh", "echo out; echo err >&2; exit 2")
except subprocess.CalledProcessError as e:
    print("CalledProcessError", e)
try:
    search_dirs("/nonexistent/python", "true")
except OSError as err:
    print("OSError", err)

client = WorkerClient("status.json", {"PATH": os.environ["PATH"]})
assert client.proc.pid > 0, f"Bad PID: {client.proc.pid}"
client.close()
print(client.proc.wait())

sys.stdout.flush()
cmd = ["sh", "-c", "echo installing $0", "types-requests"]
subprocess.run(cmd)
env = {"PATH": os.environ["PATH"]}
env["PYTHONPATH"] = "base" + os.pathsep + env.get("PYTHONPATH", "")
done = subprocess.run(["sh", "-c", "echo $PYTHONPATH; exit 3"], env=env)
print(done.returncode, time.time() > 0)
