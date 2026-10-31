"""Replay the hosted portion of #762's audit, not native execution.

Run with CPython 3.13.16: python REPLAY.py CLEAN_CHECKOUT OUTPUT.json.
The output must be outside the evaluated checkout. Run before building/testing.
Historical replay scripts using --untracked-files=no need this preflight too.
Use python -B REPLAY.py --preflight CLEAN_CHECKOUT to run only the preflight.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True)


def source_snapshot(root):
    """Fail closed on tracked, untracked AND ignored pre-existing inputs."""
    status = git(root, "status", "--porcelain=v1", "--untracked-files=all")
    ignored = git(root, "ls-files", "--others", "--ignored", "--exclude-standard", "-z")
    return {"revision": git(root, "rev-parse", "HEAD").strip(),
            "tree": git(root, "rev-parse", "HEAD^{tree}").strip(),
            "status_including_untracked": status,
            "ignored_paths": ignored.split("\0")[:-1],
            "clean_before_generation": not status and not ignored}


def provenance_controls():
    results = []
    with tempfile.TemporaryDirectory(prefix="audit-provenance-") as temp:
        root = Path(temp)
        git(root, "init", "-q")
        (root / ".gitignore").write_text("ignored.py\n")
        (root / "tracked.py").write_text("print(1)\n")
        git(root, "add", ".")
        git(root, "-c", "user.name=Audit fixture", "-c", "user.email=fixture@example.invalid",
            "commit", "-qm", "Temporary provenance fixture")
        assert source_snapshot(root)["clean_before_generation"]
        results.append({"case": "clean tracked fixture", "passed": True})
        for name in ("lib/untracked.py", "tests/untracked.py", "ignored.py"):
            path = root / name
            path.parent.mkdir(exist_ok=True)
            path.write_text("print(2)\n")
            snapshot = source_snapshot(root)
            assert not snapshot["clean_before_generation"]
            results.append({"case": name, "passed": True, "snapshot": snapshot})
            path.unlink()
        (root / "tracked.py").write_text("print(3)\n")
        snapshot = source_snapshot(root)
        assert not snapshot["clean_before_generation"]
        results.append({"case": "modified tracked input", "passed": True, "snapshot": snapshot})
    return results


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--preflight":
        snapshot = source_snapshot(Path(sys.argv[2]).resolve())
        print(json.dumps(snapshot, indent=2))
        raise SystemExit(0 if snapshot["clean_before_generation"] else 1)
    root, output = (Path(p).resolve() for p in sys.argv[1:])
    if output == root or root in output.parents:
        raise SystemExit("Write evidence outside the evaluated checkout")
    before = source_snapshot(root)
    if not before["clean_before_generation"]:
        raise SystemExit("Preflight rejected non-pristine source: " + json.dumps(before))
    environment = {k: v for k, v in os.environ.items()
                   if not k.startswith("PYSTACHY_") and k not in ("PYTHONPATH", "PYTHONHOME")}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    records = []

    def run(command, *, ir=False, expect=0):
        result = subprocess.run(command, cwd=root, env=environment,
                                capture_output=True, timeout=180)
        record = {"command": command, "exit": result.returncode, "expected_exit": expect,
                  "passed": result.returncode == expect,
                  "stderr": result.stderr.decode(errors="replace")}
        if ir:
            record.update(stdout_bytes=len(result.stdout),
                          stdout_sha256=hashlib.sha256(result.stdout).hexdigest())
        else:
            record["stdout"] = result.stdout.decode(errors="replace")
        records.append(record)
        return result

    data = {"status": "incomplete-native-toolchain-unavailable", "source_before": before,
            "python": sys.version, "python_executable": sys.executable,
            "native_compiler": None, "llvm": None, "records": records,
            "provenance_controls": provenance_controls()}
    for pattern in ("test_release*.py", "test_workflow_limits.py"):
        run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tools", "-p", pattern, "-v"])
    run(["sh", "-n", "tools/docker_smoke.sh"])
    fixtures = ("lib_difflib", "lib_difflib_grouped", "lib_difflib_unified")
    data["fixture_sha256"] = {}
    for name in fixtures:
        path = root / "tests" / (name + ".py")
        expected = (path.with_suffix(".out")).read_bytes()
        result = run([sys.executable, "-B", str(path)])
        # Recordings append the harness exit marker, which is not program stdout.
        records[-1]["recording_matches"] = result.stdout + b"[exit 0]\n" == expected
        records[-1]["passed"] &= records[-1]["recording_matches"] and not result.stderr
        data["fixture_sha256"][str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        run([sys.executable, "-B", "pystachy.py", "ir", str(path)], ir=True)
    programs = {
        "context_diff": "import difflib\nprint(list(difflib.context_diff(['a\\n'], ['b\\n'])))\n",
        "ndiff": "import difflib\nprint(list(difflib.ndiff(['a\\n'], ['b\\n'])))\n",
        "Differ": "import difflib\nprint(list(difflib.Differ().compare(['a\\n'], ['b\\n'])))\n",
        "HtmlDiff": "import difflib\nprint(difflib.HtmlDiff().make_table(['a'], ['b']))\n",
    }
    data["boundary_programs"] = programs
    with tempfile.TemporaryDirectory(prefix="audit-release-probes-") as temp:
        for name, program in programs.items():
            path = Path(temp) / (name + ".py")
            path.write_text(program)
            run([sys.executable, "-B", str(path)])
            run([sys.executable, "-B", "pystachy.py", "ir", str(path)], ir=True, expect=1)
    data["source_after"] = source_snapshot(root)
    data["all_selected_hosted_checks_pass"] = all(r["passed"] for r in records)
    output.write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps({"records": len(records), "all_passed": data["all_selected_hosted_checks_pass"],
                      "source_clean_after": data["source_after"]["clean_before_generation"]}))


if __name__ == "__main__":
    main()
