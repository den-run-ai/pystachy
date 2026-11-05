"""Install the hosted compiler with pip and uv, then exercise both commands."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from install_smoke import PROGRAM, execute

ROOT = Path(__file__).resolve().parents[1]


def check_install(command, python, directory, environment, revision):
    environment = dict(environment, XDG_CACHE_HOME=str(directory / f"{python.parent.parent.name} cache"))
    program = directory / "demo.py"
    expected = execute([sys.executable, str(program)], directory, environment)
    version = (ROOT / "VERSION").read_text().strip()
    if not execute([str(command), "--version"], directory,
                   dict(environment, PYSTACHY_LLVM="/unavailable")).startswith(f"pystachy {version} (commit "):
        raise RuntimeError(f"unexpected compiler version from {command}")
    if revision:
        read_revision = (
            "import json; from importlib.metadata import distribution; "
            "print(json.loads(distribution('pystachy').read_text('direct_url.json'))"
            "['vcs_info']['commit_id'])"
        )
        if execute([str(python), "-c", read_revision], directory, environment).strip() != revision:
            raise RuntimeError(f"wrong Git revision installed by {command}")
    if execute([str(command), "run", str(program)], directory, environment) != expected:
        raise RuntimeError(f"JIT output differs from CPython: {command}")
    executable = directory / "demo"
    executable.unlink(missing_ok=True)
    execute([str(command), "build", str(program), "-o", str(executable)], directory, environment)
    if execute([str(executable)], directory, dict(environment, PATH="")) != expected:
        raise RuntimeError(f"AOT output differs from CPython: {command}")
    cache = Path(environment["XDG_CACHE_HOME"]) / "pystachy"
    if not list(cache.glob("runtime-*.bc")):
        raise RuntimeError(f"the installed compiler did not use its external cache: {cache}")
    print(f"{command}: version, JIT, standalone AOT and external cache passed", flush=True)


def smoke(source, revision):
    environment = {name: value for name, value in os.environ.items()
                   if not name.startswith("PYSTACHY_") or name == "PYSTACHY_LLVM"}
    for name in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
        environment.pop(name, None)
    with tempfile.TemporaryDirectory(prefix="pystachy-compiler-install-") as temporary:
        directory = Path(temporary) / "outside checkout"
        directory.mkdir()
        (directory / "demo.py").write_text(PROGRAM, encoding="utf-8")

        def run(*command):
            subprocess.run(command, cwd=directory, env=environment, check=True, timeout=300)

        venv = directory / "pip env"
        run(sys.executable, "-m", "venv", str(venv))
        pip_python = venv / "bin/python"
        pip = (str(pip_python), "-m", "pip", "--disable-pip-version-check")
        run(*pip, "install", "--no-deps", source)
        pip_cli = venv / "bin/pystachy"
        check_install(pip_cli, pip_python, directory, environment, revision)
        run(*pip, "uninstall", "-y", "pystachy")
        if pip_cli.exists():
            raise RuntimeError("pip uninstall left the command installed")

        uv_tools = directory / "uv-tools"
        uv_bin = directory / "uv-bin"
        environment.update(UV_TOOL_DIR=str(uv_tools), UV_TOOL_BIN_DIR=str(uv_bin),
                           UV_CACHE_DIR=str(directory / "uv-cache"))
        run("uv", "tool", "install", "--python", sys.executable, "--no-python-downloads", source)
        uv_cli = uv_bin / "pystachy"
        check_install(uv_cli, uv_tools / "pystachy/bin/python", directory, environment, revision)
        run("uv", "tool", "uninstall", "pystachy")
        if uv_cli.exists() or uv_cli.is_symlink():
            raise RuntimeError("uv tool uninstall left the command installed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(ROOT), help="local checkout or a direct Git requirement")
    parser.add_argument("--revision", help="expected full Git commit in installed provenance")
    args = parser.parse_args()
    smoke(args.source, args.revision)


if __name__ == "__main__":
    main()
