"""Install a native JSON-repair wheel offline and check it outside the checkout.

The maintained API corpus runs normally and with forced GC. The installed command
uses the existing CLI cases without Python/LLVM on PATH. Spawned workers each
import the extension; calls from another host thread must still be rejected.
"""

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
from importlib import metadata
from importlib.machinery import ExtensionFileLoader
import json
import multiprocessing
import os
from pathlib import Path
import platform
import re
import runpy
import signal
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "pystachy_json_repair"


def sha256(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def clean_environment():
    return {name: value for name, value in os.environ.items()
            if not name.startswith(("PYTHON", "PYSTACHY_")) and name != "VIRTUAL_ENV"} | {"LC_ALL": "C"}


def execute(command, directory, environment, timeout=180):
    # The installed probe spawns workers. A timeout must stop their whole process
    # group, including when the probe exits but a worker still owns an output pipe.
    with subprocess.Popen(command, cwd=directory, env=environment, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, start_new_session=True) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            if process.returncode:
                raise RuntimeError(f"{command!r}: exit {process.returncode}\n{stdout}\n{stderr}")
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise
    return stdout


def corpus_summary(output, count):
    summaries = re.findall(r"^(\d+)/(\d+) match; (\d+) problems$", output, re.MULTILINE)
    if count <= 0 or summaries != [(str(count), str(count), "0")]:
        raise ValueError(f"the installed replay did not confirm all {count} cases:\n{output}")
    return {"cases": count, "matched": count, "problems": 0}


def installed_package(prefix):
    """Reject source/fallback imports and files not owned by this installation."""
    prefix = prefix.resolve()
    if Path(sys.prefix).resolve() != prefix or sys.prefix == sys.base_prefix or not sys.flags.isolated:
        raise ValueError("the installed probe must run in its isolated virtual environment")
    import pystachy_json_repair as companion

    extension = companion._native
    if not isinstance(extension.__spec__.loader, ExtensionFileLoader):
        raise ValueError(f"expected a real compiled extension: {extension.__file__}")
    distribution = metadata.distribution("pystachy-json-repair")
    files = {str(path): path for path in distribution.files or []}
    for module, filename in [(companion, "__init__.py"), (extension, "_native.abi3.so")]:
        origin = Path(module.__file__).resolve()
        record = files.get(f"{PACKAGE}/{filename}")
        if (not origin.is_relative_to(prefix) or origin.is_relative_to(ROOT)
                or record is None or Path(distribution.locate_file(record)).resolve() != origin):
            raise ValueError(f"module is not owned by the installed wheel: {origin}")
        digest = base64.urlsafe_b64encode(bytes.fromhex(sha256(origin))).rstrip(b"=").decode("ascii")
        if record.hash is None or record.hash.mode != "sha256" or record.hash.value != digest:
            raise ValueError(f"installed file differs from its wheel RECORD: {origin}")
    return companion, {"package_version": distribution.version,
                       "package_origin": str(Path(companion.__file__).resolve()),
                       "extension_origin": str(Path(extension.__file__).resolve()),
                       "extension_sha256": sha256(Path(extension.__file__))}


def repair_checks(companion):
    # Both calls enter native repair, including loads() which bypasses native
    # code for valid JSON. Keep the original input malformed.
    text = '{worker: [1, true, null,],}'
    for _ in range(8):
        value = companion.loads(text)
        if (value != {"worker": [1, True, None]} or type(value["worker"][0]) is not int
                or type(value["worker"][1]) is not bool):
            raise ValueError("installed object repair changed values or types")
        if companion.repair_json(text) != '{"worker": [1, true, null]}':
            raise ValueError("installed text repair changed output")


def process_worker(prefix, connection):
    try:
        companion, identity = installed_package(prefix)
        repair_checks(companion)
        connection.send(identity | {"pid": os.getpid()})
    finally:
        connection.close()


def close_workers(workers):
    failures = []
    for worker, receive in workers:
        try:
            try:
                if worker.pid is not None:
                    if worker.is_alive():
                        worker.terminate()
                    worker.join(5)
                    if worker.is_alive():
                        worker.kill()
                        worker.join()
                worker.close()
            finally:
                receive.close()
        except BaseException as error:
            # A cleanup failure for one worker must not abandon the others.
            failures.append(error)
    if failures:
        raise failures[0]


def process_checks(prefix, expected):
    context = multiprocessing.get_context("spawn")
    workers = []
    try:
        for _ in range(2):
            receive, send = context.Pipe(duplex=False)
            try:
                worker = context.Process(target=process_worker, args=(prefix, send))
            except BaseException:
                receive.close()
                send.close()
                raise
            workers.append((worker, receive))
            try:
                worker.start()
            finally:
                send.close()
        identities = []
        for worker, receive in workers:
            if not receive.poll(30):
                raise RuntimeError("installed process worker did not return a result")
            identity = receive.recv()
            worker.join(30)
            if worker.exitcode != 0:
                raise RuntimeError(f"installed process worker exited {worker.exitcode}")
            if any(identity.get(key) != value for key, value in expected.items()):
                raise ValueError("a process worker loaded a different installation")
            identities.append(identity)
        if len({identity["pid"] for identity in identities}) != 2:
            raise ValueError("expected two independent spawned process workers")
        return len(identities)
    finally:
        original = sys.exception()
        try:
            close_workers(workers)
        except BaseException as error:
            if original is None:
                raise
            original.add_note(f"Worker cleanup also failed: {error!r}")


def installed_probe(prefix):
    companion, identity = installed_package(prefix)
    repair_checks(companion)
    rejected = 0
    with ThreadPoolExecutor(max_workers=1) as pool:
        for method in (companion.loads, companion.repair_json):
            try:
                pool.submit(method, '{thread: true,}').result(timeout=30)
            except RuntimeError as error:
                if "thread that imported its module" not in str(error):
                    raise
                rejected += 1
            else:
                raise ValueError("native repair unexpectedly accepted a foreign host thread")
    # A rejected thread entry must not poison later calls by the importing thread.
    repair_checks(companion)
    return identity | {"python": platform.python_version(), "implementation": sys.implementation.name,
                       "thread_rejections": rejected, "spawned_processes": process_checks(prefix, identity)}


def smoke(wheel, root=None):
    wheel = wheel.resolve(strict=True)
    root = ROOT if root is None else root.resolve()
    suite = root / "tests/upstream/json_repair"
    cases_path = suite / "cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("the installed-wheel check requires a nonempty API corpus")
    probe_path = Path(__file__).resolve()
    paths = [cases_path, suite / "extension.py", suite / "replay.py", suite / "cli.py",
             root / "tools/json_repair_parity.py", probe_path]
    inputs = {path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path): path
              for path in paths}
    identities = {name: sha256(path) for name, path in inputs.items()}
    wheel_digest = sha256(wheel)
    environment = clean_environment()
    with tempfile.TemporaryDirectory(prefix="pystachy-json-repair-wheel-") as temporary:
        directory = Path(temporary).resolve()
        if directory.is_relative_to(root):
            raise ValueError("choose a TMPDIR outside the checkout for the installed-wheel check")
        work = directory / "outside checkout"
        work.mkdir()
        prefix = directory / "venv"
        execute([sys.executable, "-I", "-m", "venv", str(prefix)], work, environment)
        python = str(prefix / "bin/python")  # Do not resolve the venv's interpreter symlink.
        execute([python, "-I", "-m", "pip", "--isolated", "install", "--no-index", "--no-deps",
                 "--no-cache-dir", "--disable-pip-version-check", str(wheel)], work, environment)
        probe = execute([python, "-I", str(probe_path), "--installed-prefix", str(prefix)],
                        work, environment)
        installed = json.loads(probe)
        modes = {}
        for mode, env in [("normal", environment), ("forced_gc", environment | {"PYSTACHY_GC_STRESS": "1"})]:
            output = execute([python, "-I", str(suite / "extension.py")], work, env)
            modes[mode] = corpus_summary(output, len(cases))
            print(f"installed API ({mode}): {len(cases)}/{len(cases)} corpus cases", flush=True)

        # Reuse the maintained expected argv/stream/file effects, including
        # failed inline writes, malformed UTF-8, lone surrogates and wide ints.
        cli_suite = runpy.run_path(str(suite / "cli.py"))
        console = prefix / "bin/json-repair-native"
        for case in cli_suite["CASES"]:
            _, stderr = cli_suite["run_case"]([str(console)], case, environment | {"PATH": ""})
            if case.status != 0 and not stderr:
                raise ValueError(f"installed CLI omitted the error diagnostic for {case.args}")
        cli_cases = len(cli_suite["CASES"])
        if not cli_cases:
            raise ValueError("the installed-wheel check requires CLI cases")
        print(f"installed CLI: {cli_cases} cases; spawned workers: {installed['spawned_processes']}; "
              f"thread rejections: {installed['thread_rejections']}", flush=True)

    if wheel_digest != sha256(wheel) or identities != {
            name: sha256(path) for name, path in inputs.items()}:
        raise ValueError("wheel or validation inputs changed during the installed check")
    return {"schema_version": 1, "wheel": wheel.name, "wheel_sha256": wheel_digest,
            "installation": installed, "corpus": modes, "cli_cases": cli_cases,
            "validation_inputs": identities}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path, nargs="?", help="locally built wheel to install and check")
    parser.add_argument("--json", type=Path, help="save the completed validation report")
    parser.add_argument("--installed-prefix", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.installed_prefix:
            print(json.dumps(installed_probe(args.installed_prefix), sort_keys=True))
            return 0
        if args.wheel is None:
            parser.error("provide a wheel")
        if args.json and args.json.resolve() == args.wheel.resolve():
            parser.error("the report path must not replace the wheel")
        report = smoke(args.wheel)
        if args.json:
            args.json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, RuntimeError, EOFError, subprocess.SubprocessError) as error:
        parser.exit(1, f"json-repair wheel smoke: {error}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
