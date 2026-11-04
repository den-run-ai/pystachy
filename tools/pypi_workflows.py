"""Check selected unchanged PyPI packages against CPython in separate wheel installations.

See tests/upstream/pypi/README.md for inputs, scope and commands. Bulk inventory
entries are never executed. Each named case uses its project's complete locked wheel.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile

from import_sweep import compiler_sha256
from pypi_import_ir import attributed_ir

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "tests/upstream/pypi/requirements.txt"

# Project, public import, and a deterministic API call. All wheels have zero
# mandatory dependencies under the pinned interpreter, without extras.
APIS = {
    "argparse-addons": ("argparse_addons", """import argparse
convert = argparse_addons.Integer(1, 16)
print(convert("0x0f"))
try:
    convert("17")
except argparse.ArgumentTypeError as e:
    print(type(e).__name__, str(e))
"""),
    "astpretty": ("astpretty", "import ast\nprint(astpretty.pformat(ast.parse('x + 1')))"),
    "cycler": ("cycler", "print(cycler.cycler(color=['red', 'blue']).by_key()['color'])"),
    "distro": ("distro", "print(distro.LinuxDistribution(include_lsb=False, include_uname=False, "
                         "include_oslevel=False, os_release_file='os-release').id())"),
    "docx2txt": ("docx2txt", "from docx2txt.docx2txt import xml2text\n"
                            "print(xml2text('<w:t xmlns:w=\"http://schemas.openxmlformats.org/"
                            "wordprocessingml/2006/main\">hello</w:t>'))"),
    "jmespath": ("jmespath", "print(jmespath.search('a[0]', {'a': [17, 18]}))"),
    "packaging": ("packaging", "from packaging.version import Version\nprint(Version('2.0') > Version('1.9'))"),
    "pyhumps": ("humps", "print(humps.camelize('some_name'))"),
    "roman": ("roman", "print(roman.toRoman(944), roman.fromRoman('mcmxcix'))"),
    "tokenize-rt": ("tokenize_rt", "print(tokenize_rt.tokens_to_src(tokenize_rt.src_to_tokens('x = 1')))"),
    "urllib3": ("urllib3", "from urllib3.util import parse_url\nprint(parse_url('https://example.org/p').host)"),
}
ROMAN_SDIST = "275fe9f46290f7d0ffaea1c33251b92b8e463ace23660508ceef522e7587cb6f"
ROMAN_FILE_WORKFLOW = """import roman
import argparse

parser = argparse.ArgumentParser(prog='convert')
parser.add_argument('source')
parser.add_argument('target')
args = parser.parse_args()
with open(args.source) as source:
    value = roman.fromRoman(source.read().strip())
with open(args.target, 'w') as target:
    target.write(roman.toRoman(value + 1) + '\\n')
"""
ROMAN_TEST_RUNNER = """import sys
import unittest
from upstream_tests import test_suite
suite = test_suite()
original_stdout = sys.stdout
result = suite.run(unittest.TestResult())
sys.stdout = original_stdout
assert result.testsRun == 8 and result.wasSuccessful()
print(result.testsRun)
"""


def checked_file(path, digest):
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError(f"unexpected SHA-256 for {path.name}")


def cases(project, site, wheels):
    module, api = APIS[project]
    prefix = f"import {module}\n"
    yield "import", prefix + "print('imported')\n", []
    yield "api", prefix + api + "\n", []
    if project == "argparse-addons":
        yield "log_level_api", prefix + "print(argparse_addons.parse_log_level('worker,parser=DEBUG:WARN'))\n", []
    if project == "roman":
        yield "file_workflow", ROMAN_FILE_WORKFLOW, ["input.txt", "output.txt"]
        yield "upstream_cli", prefix + "import sys\nsys.exit(roman.main())\n", ["-r", "mcmxcix"]
        # The wheel omits the upstream tests. Load only the named test module
        # from its matching pinned sdist and execute its actual suite.
        sdist = wheels / "roman-5.2.tar.gz"
        checked_file(sdist, ROMAN_SDIST)
        with tarfile.open(sdist) as archive:
            (site / "upstream_tests.py").write_bytes(archive.extractfile("roman-5.2/src/tests.py").read())
        yield "upstream_tests", ROMAN_TEST_RUNNER, []


def command(argv, env, work, timeout):
    try:
        p = subprocess.run(argv, env=env, cwd=work, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"timeout": timeout}
    return {"exit": p.returncode, "stdout": p.stdout.decode(errors="surrogateescape"),
            "stderr": p.stderr.decode(errors="surrogateescape")}


def execute(argv, env, work, timeout, file_workflow):
    output = work / "output.txt"
    output.unlink(missing_ok=True)
    result = command(argv, env, work, timeout)
    if file_workflow:
        result["output_file_hex"] = output.read_bytes().hex() if output.is_file() else None
    return result


def stage(result, reference=None, replacements=()):
    if "timeout" in result:
        return result
    if result["exit"] == 0 and (reference is None or result == reference):
        return "pass"
    if reference is not None and result["exit"] == 0:
        return {"mismatch": result}
    diagnostic = result["stderr"].strip() or result["stdout"].strip()
    for path, label in replacements:
        diagnostic = diagnostic.replace(str(path), label)
    return {"exit": result["exit"], "diagnostic": diagnostic}


def probe(kind, program, args, work, target, compiler, env, timeout):
    driver = work / "probe.py"
    driver.write_text(program)
    file_workflow = kind == "file_workflow"
    reference = execute([sys.executable, "-BS", "probe.py", *args], env, work, timeout, file_workflow)
    if reference.get("exit") != 0 or (file_workflow and reference["output_file_hex"] is None):
        raise RuntimeError(f"{kind}: CPython oracle failed: {reference}")
    run = {"cpython": reference, "ir": None, "jit": "not run", "build": "not run", "aot": "not run"}
    ir = attributed_ir(compiler, env, driver, target, timeout)
    if ir["status"] != "ir":
        run["ir"] = ir
        return run
    run["ir"] = "pass"
    replacements = [(env["PYSTACHY_PATH"], "SITE"), (work, "WORK"), (compiler.parent, "COMPILER")]
    jit = execute([compiler, "run", "probe.py", *args], env, work, timeout, file_workflow)
    run["jit"] = stage(jit, reference, replacements)
    exe = work / "probe-bin"
    exe.unlink(missing_ok=True)
    run["build"] = stage(command([compiler, "build", "probe.py", "-o", exe], env, work, timeout),
                         replacements=replacements)
    if run["build"] == "pass" and not exe.is_file():
        run["build"] = {"exit": 0, "diagnostic": "compiler did not produce an executable"}
    if run["build"] == "pass":
        run["aot"] = stage(execute([exe, *args], env, work, timeout, file_workflow), reference, replacements)
    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheelhouse", type=Path)
    parser.add_argument("--compiler", type=Path, default=ROOT / "pystachy")
    parser.add_argument("--project", choices=sorted(APIS))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    compiler = args.compiler.resolve(strict=True)
    wheels = args.wheelhouse.resolve(strict=True)
    if not (compiler.parent / "runtime.c").is_file():
        parser.error("--compiler must be a bootstrapped binary in its source checkout")
    if platform.python_version() != (ROOT / ".python-version").read_text().strip():
        parser.error("run using the repository's pinned CPython")
    uv = shutil.which("uv")
    if uv is None:
        parser.error("uv is required to install the locked wheels")
    revision = subprocess.check_output(["git", "-C", compiler.parent, "rev-parse", "HEAD"], text=True).strip()
    llvm_bin = os.getenv("PYSTACHY_LLVM")
    llvm = str(Path(llvm_bin) / "lli") if llvm_bin else "lli"
    tree = subprocess.check_output(["git", "-C", compiler.parent, "rev-parse", "HEAD^{tree}"], text=True).strip()
    report = {"compiler_checkout": revision, "compiler_tree": tree, "compiler_sha256": compiler_sha256(compiler),
              "argparse_sha256": compiler_sha256(compiler.parent / "lib" / "argparse.py"),
              "cpython": platform.python_version(), "llvm": subprocess.check_output([llvm, "--version"], text=True).splitlines()[0],
              "timeout_s": args.timeout, "projects": {}}
    env = {k: os.environ[k] for k in ("PATH", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "SDKROOT")
           if k in os.environ}
    if llvm_bin:
        env["PYSTACHY_LLVM"] = llvm_bin
    with tempfile.TemporaryDirectory(prefix="pystachy-pypi-") as directory:
        base = Path(directory)
        (base / "home").mkdir()
        env.update(HOME=str(base / "home"), PYSTACHY_HOME=str(compiler.parent), PYSTACHY_CACHE=str(base / "cache"),
                   PYTHONHASHSEED="0", LC_ALL="C", TZ="UTC")
        for line in LOCK.read_text().splitlines():
            requirement, sha = line.split(" --hash=sha256:")
            project, version = requirement.split("==")
            if args.project and project != args.project:
                continue
            wheel, = wheels.glob(f"{project.replace('-', '_')}-{version}-*.whl")
            checked_file(wheel, sha)
            site = base / project / "site"
            subprocess.run([uv, "--no-config", "--offline", "--no-cache", "pip", "install", "--no-index",
                            "--no-python-downloads", "--python", sys.executable, "--target", site, wheel],
                           check=True, capture_output=True, env=env, cwd=base, timeout=args.timeout)
            env.update(PYTHONPATH=str(site), PYSTACHY_PATH=str(site))
            # Verify the public import is provided by this wheel, even if a
            # similarly named module exists on the machine running the probe.
            origin_check = ("import importlib.util, pathlib, sys; "
                            "print(pathlib.Path(importlib.util.find_spec(sys.argv[1]).origin).resolve())")
            target = Path(subprocess.check_output([sys.executable, "-BS", "-c", origin_check, APIS[project][0]],
                          cwd=base, env=env, text=True, timeout=args.timeout).strip())
            if not target.is_relative_to(site) or target.suffix != ".py" or not target.is_file():
                raise ValueError(f"{project}: expected a Python source file inside its wheel installation")
            result = {}
            for kind, program, extra in cases(project, site, wheels):
                work = site.parent / kind
                work.mkdir()
                (work / "input.txt").write_text("mcmxcix\n")
                (work / "os-release").write_text('ID=example\nNAME="Fixture OS"\n')
                result[kind] = probe(kind, program, extra, work, target, compiler, env, args.timeout)
            report["projects"][project] = {"wheel": wheel.name, "sha256": sha, "cases": result}
            print(project, {k: v["aot"] for k, v in result.items()}, flush=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
