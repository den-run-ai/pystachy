"""Differential integration check for the three flow-analysis prototypes."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/flow_analysis.py"


def run(command, env, timeout=180):
    return subprocess.run(command, cwd=ROOT, env=env, text=True,
                          capture_output=True, timeout=timeout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default="./pystachy",
                        help="bootstrapped native compiler executable")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    compiler = str(Path(args.compiler).resolve())
    environment = dict(os.environ, PYSTACHY_HOME=str(ROOT),
                       PYSTACHY_FLOW_LOCALS="1", PYSTACHY_CLOSED_UNIONS="1",
                       PYSTACHY_IRCHECK="1")
    environment.pop("PYSTACHY_SUMMARY_STATS", None)
    checks = []
    outputs = {}

    def check(name, command, expected, env=environment):
        result = run(command, env)
        actual = (result.returncode, result.stdout, result.stderr)
        if actual != expected:
            raise RuntimeError(f"{name}: expected {expected!r}, got {actual!r}")
        checks.append(name)

    with tempfile.TemporaryDirectory(prefix="pystachy-flow-analysis-") as temporary:
        directory = Path(temporary)
        fixtures = ROOT / "tests/prototypes/closed_unions"
        sources = [EXAMPLE, *sorted(fixtures.glob("*.py"))]
        compilers = (("hosted", [sys.executable, "-m", "pystachy"]), ("native", [compiler]))
        for source in sources:
            reference = run([sys.executable, str(source)], environment)
            if reference.returncode or reference.stderr:
                raise RuntimeError("CPython fixture failed: " + reference.stderr)
            expected = (0, reference.stdout, "")
            outputs[str(source.relative_to(ROOT))] = reference.stdout
            irs = []
            for label, command in compilers:
                name = source.stem + "-" + label
                ir = directory / (name + ".ll")
                result = run([*command, "ir", str(source), "-o", str(ir)], environment)
                if result.returncode or result.stderr:
                    raise RuntimeError(name + " IR failed: " + result.stderr)
                irs.append(ir.read_bytes())
                checks.append(name + "-ir")
                check(name + "-jit", [*command, "run", str(source)], expected)
                binary = directory / name
                result = run([*command, "build", str(source), "-o", str(binary)], environment)
                if result.returncode or result.stderr:
                    raise RuntimeError(name + " AOT build failed: " + result.stderr)
                check(name + "-aot", [str(binary)], expected)
                check(name + "-aot-gc-stress", [str(binary)], expected,
                      dict(environment, PYSTACHY_GC_STRESS="1"))
            if irs[0] != irs[1]:
                raise RuntimeError("hosted and native compilers emitted different IR: " + source.name)
            checks.append(source.stem + "-hosted-native-ir-identical")
        for source in sorted((fixtures / "errors").glob("*.py")):
            marker = "# expected: "
            first = source.read_text().splitlines()[0]
            if not first.startswith(marker):
                raise RuntimeError("missing rejection expectation: " + str(source))
            for label, command in compilers:
                result = run([*command, "ir", str(source), "-o", str(directory / "reject.ll")], environment)
                if result.returncode != 1 or first[len(marker):] not in result.stderr:
                    raise RuntimeError(source.name + " rejection changed: " + result.stderr)
                checks.append(source.stem + "-" + label + "-rejected")
        # Unsupported syntax remains rejected unless the experiment is enabled.
        disabled = dict(environment, PYSTACHY_FLOW_LOCALS="0", PYSTACHY_CLOSED_UNIONS="0")
        result = run([compiler, "ir", str(EXAMPLE), "-o", str(directory / "off.ll")], disabled)
        if result.returncode != 1 or "error:" not in result.stderr:
            raise RuntimeError("disabled experiment unexpectedly accepted the example: " + result.stderr)
        checks.append("disabled-union-rejected")

    report = {"python": sys.version.split()[0], "compiler": compiler,
              "flags": {"PYSTACHY_FLOW_LOCALS": "1", "PYSTACHY_CLOSED_UNIONS": "1"},
              "outputs": outputs,
              "checks": checks, "passed": len(checks), "failed": 0}
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Flow-analysis integration: {len(checks)} passed, 0 failed")


if __name__ == "__main__":
    main()
