"""Build the optional bridge and compare CPython/native TCP exchanges on loopback."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


class Peer:
    """An independent stdlib peer; no libuv or Pystachy imports."""

    def __init__(self):
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(128)
        self.listener.settimeout(0.1)
        self.port = self.listener.getsockname()[1]
        self.refused = socket.socket()
        self.refused.bind(("127.0.0.1", 0))
        self.refused_port = self.refused.getsockname()[1]
        self.stop = threading.Event()
        self.release = threading.Event()
        self.pool = ThreadPoolExecutor(max_workers=8)
        self.futures = []
        self.thread = threading.Thread(target=self.accept)

    def accept(self):
        while not self.stop.is_set():
            try:
                connection, _ = self.listener.accept()
            except socket.timeout:
                continue
            self.futures.append(self.pool.submit(self.serve, connection))

    def serve(self, connection):
        with connection:
            connection.settimeout(5)
            try:
                payload = bytearray()
                while part := connection.recv(4096):
                    payload += part
                    if len(payload) > 65536:
                        raise AssertionError("peer received an unexpectedly large request")
                request = bytes(payload)
                if request == b"wait":
                    self.stop.wait(0.25)
                    return
                if request == b"hold":
                    if not self.release.wait(4):
                        raise AssertionError("held request was never released")
                    response = b"slow"
                elif request == b"release":
                    self.release.set()
                    response = b"released"
                elif request == b"limit":
                    response = b"x" * 16
                elif request == b"overflow":
                    response = b"x" * 17
                elif request.startswith(b"E"):
                    response = request[1:]
                elif not request:
                    response = b""
                else:
                    raise AssertionError(f"unknown peer command: {request!r}")
                for start in range(0, len(response), 2048):
                    connection.sendall(response[start:start + 2048])
            except (ConnectionResetError, BrokenPipeError):
                pass  # A canceled request is allowed to close in any transport phase.

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.release.set()
        self.thread.join(5)
        self.listener.close()
        self.refused.close()
        self.pool.shutdown(wait=True)
        if self.thread.is_alive():
            raise AssertionError("peer accept thread did not terminate")
        for future in self.futures:
            future.result()


def socket_oracle(peer):
    """Verify the exchange contract independently with CPython's socket module."""
    for payload in [b"", b"E\0\xffA\0B", b"E" + b"x" * 32768, b"limit", b"overflow"]:
        with socket.create_connection(("127.0.0.1", peer.port), timeout=3) as connection:
            connection.sendall(payload)
            connection.shutdown(socket.SHUT_WR)
            result = bytearray()
            while part := connection.recv(4096):
                result += part
        expected = payload[1:] if payload.startswith(b"E") else {
            b"": b"", b"limit": b"x" * 16, b"overflow": b"x" * 17,
        }[payload]
        if bytes(result) != expected:
            raise AssertionError("stdlib socket oracle disagrees with peer")
    with socket.create_connection(("127.0.0.1", peer.port), timeout=3) as connection:
        connection.sendall(b"wait")
        connection.shutdown(socket.SHUT_WR)
        connection.settimeout(0.05)
        try:
            connection.recv(1)
        except TimeoutError:
            pass
        else:
            raise AssertionError("stdlib socket oracle expected a deadline")


def run(command, env, timeout=180):
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException as error:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = process.communicate(timeout=5)
        if isinstance(error, subprocess.TimeoutExpired):
            raise RuntimeError(f"{shlex.join(command)} timed out after {timeout}s\n"
                               + stderr.decode("utf-8", "replace")[-8000:]) from error
        raise
    if process.returncode or stderr:
        raise RuntimeError(f"{shlex.join(command)} exited {process.returncode}\n"
                           + stderr.decode("utf-8", "replace")[-8000:])
    return stdout


def source_hashes():
    names = ["bridge.c", "bridge.h", "uvio.py", "exercise.py", "ownership.c", "hosted.py", "check.py"]
    return {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in names}


def verify_sources(before, report):
    after = source_hashes()
    report["sources_after"] = after
    if before != after:
        raise RuntimeError("consumed sources changed during the check; rerun from a fixed tree")


def write_report(path, report):
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n")


def check(args, report):
    if args.leak_check and not args.sanitizers:
        raise ValueError("--leak-check requires --sanitizers")
    if sys.platform != "linux":
        raise ValueError("the example build and descriptor probe currently target Linux")
    if not 1 <= args.repeat <= 64:
        raise ValueError("--repeat must be between 1 and 64")
    before = source_hashes()
    report["sources_before"] = before
    if args.libuv_prefix:
        prefix = args.libuv_prefix.resolve()
        cflags = ["-I" + str(prefix / "include")]
        libraries = ["-L" + str(prefix / "lib"), "-Wl,-rpath," + str(prefix / "lib"), "-luv"]
    else:
        cflags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "libuv"], text=True))
        libraries = shlex.split(subprocess.check_output(["pkg-config", "--libs", "libuv"], text=True))
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("PYSTACHY_") and key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONOPTIMIZE"}}
    # The local runtime tree is identical to the separately built compiler's recorded base.
    env["PYSTACHY_HOME"] = str(ROOT)
    env["PYSTACHY_PATH"] = str(HERE)
    env["PYTHONPATH"] = str(ROOT / "tools" / "rt_cpython") + os.pathsep + str(HERE)
    common = shlex.split(args.cc) + ["-std=c11", "-D_GNU_SOURCE", "-Wall", "-Wextra", "-Werror", "-g"]
    compiler = shlex.split(args.compiler)
    report.update({
        "platform": platform.platform(), "python": sys.version,
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "repeat": args.repeat, "runs": {},
        "cc_version": subprocess.check_output(shlex.split(args.cc) + ["--version"], text=True).splitlines()[0],
        "compiler_command": None if args.cpython_only else compiler,
    })
    if not args.cpython_only:
        candidate = ROOT / compiler[0]
        compiler_file = candidate if candidate.is_file() else Path(shutil.which(compiler[0]) or compiler[0])
        if compiler_file.is_file():
            report["compiler_sha256"] = hashlib.sha256(compiler_file.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="pystachy-uvio-") as directory:
        build = Path(directory)
        library = build / "libpystachy_uvio.so"
        run(common + ["-O2", "-shared", "-fPIC"] + cflags + [str(HERE / "bridge.c")]
            + libraries + ["-o", str(library)], env)
        native = ctypes.CDLL(str(library))
        native.uvio_version.restype = ctypes.c_char_p
        report["libuv"] = native.uvio_version().decode()
        report["bridge_sha256"] = hashlib.sha256(library.read_bytes()).hexdigest()
        env["LD_LIBRARY_PATH"] = str(build) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
        executable = build / "exercise"
        commands = [("cpython", [sys.executable, str(HERE / "exercise.py")], {})]
        if not args.cpython_only:
            # Preserve the explicit LLVM selection for compilation only.
            if "PYSTACHY_LLVM" in os.environ:
                env["PYSTACHY_LLVM"] = os.environ["PYSTACHY_LLVM"]
            run(compiler + ["build", str(HERE / "exercise.py"), "-o", str(executable)], env)
            commands += [
                ("jit", compiler + ["run", str(HERE / "exercise.py")], {}),
                ("aot", [str(executable)], {}),
                ("jit_gc", compiler + ["run", str(HERE / "exercise.py")], {"PYSTACHY_GC_STRESS_PROGRAM": "1"}),
                ("aot_gc", [str(executable)], {"PYSTACHY_GC_STRESS": "1"}),
            ]
        expected = None
        for name, command, settings in commands:
            with Peer() as peer:
                socket_oracle(peer)
                actual = run(command + [str(peer.port), str(peer.refused_port), str(args.repeat)], env | settings)
            if expected is None:
                expected = actual
            elif actual != expected:
                raise AssertionError(f"{name} differs from CPython\n{actual!r}\n{expected!r}")
            report["runs"][name] = {"stdout_sha256": hashlib.sha256(actual).hexdigest(), "gc": settings}
            print(f"{name}: exchange, completion order, bounds, deadlines and cleanup passed")
        with Peer() as peer:
            output = run([sys.executable, str(HERE / "hosted.py"), str(peer.port)], env)
        print(output.decode().strip())
        report["runs"]["hosted_lifetime"] = {"stdout_sha256": hashlib.sha256(output).hexdigest()}
        probe = build / "ownership"
        instrument = ["-O1", "-fno-omit-frame-pointer", "-fsanitize=address,undefined"] if args.sanitizers else ["-O2"]
        run(common + instrument + cflags + [str(HERE / "ownership.c"), str(HERE / "bridge.c")]
            + libraries + ["-o", str(probe)], env)
        with Peer() as peer:
            output = run([str(probe), str(peer.port)], env | {"ASAN_OPTIONS": f"detect_leaks={int(args.leak_check)}:halt_on_error=1"})
        print(output.decode().strip())
        report["runs"]["ownership"] = {"sanitizers": args.sanitizers, "leak_check": args.leak_check, "exchanges": 32, "active_closes": 64}
    verify_sources(before, report)
    print(f"libuv {report['libuv']}; optional Linux TCP prototype, no asyncio compatibility claim")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"))
    parser.add_argument("--cpython-only", action="store_true")
    parser.add_argument("--libuv-prefix", type=Path, help="optional libuv install with include/ and lib/")
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--repeat", type=int, default=8)
    parser.add_argument("--sanitizers", action="store_true", help="ASan/UBSan for standalone C probe")
    parser.add_argument("--leak-check", action="store_true", help="enable LSan; requires a compatible process environment")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    report = {"result": "running", "runs": {}}
    write_report(args.json, report)
    try:
        check(args, report)
    except Exception as error:
        report["result"] = "fail"
        report["error"] = str(error)
        write_report(args.json, report)
        print(f"uvio check failed: {error}", file=sys.stderr)
        return 1
    report["result"] = "pass"
    write_report(args.json, report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
