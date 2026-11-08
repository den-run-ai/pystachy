#!/usr/bin/env python3
"""Compare an O1 Make bootstrap with this checkout's verified O2 CI bundle."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import verification_bootstrap as bundle

ROOT = Path(__file__).resolve().parents[1]


def make_bootstrap(root, env, log):
    # Force the production recipe even if a previous build has newer artifacts.
    # The workflow's existing 15-minute job limit also bounds this build.
    subprocess.run(["make", "--always-make", "--jobs=1", "pystachy",
                    "BOOTSTRAP_AOT_OPT=1", f"PY={sys.executable}"],
                   cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)


def qualify(directory, root=ROOT):
    output = root / "build/bootstrap-tier"
    output.mkdir(parents=True, exist_ok=True)
    report = {"schema": 1, "result": "fail", "temporary_aot_opt": "1", "final_aot_opt": "2",
              "performance_conclusion": "inconclusive"}
    with (output / "make.log").open("w") as log:
        try:
            files, standard = bundle.load_bundle(directory, root)
            report.update(identity=bundle.identity(root),
                          standard_bootstrap_bundle_id=standard["bootstrap_bundle_id"],
                          standard_bootstrap_seconds=standard["producer_seconds"])
            producer_report = bundle.read_file(root / "build/verification.json")
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith("PYSTACHY_") and key not in
                   ("MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES", "MAKEFILES", "GNUMAKEFLAGS")}
            env.update(PYSTACHY_HOME=str(root), PYSTACHY_JOBS="2")
            if "PYSTACHY_LLVM" in os.environ:
                env["PYSTACHY_LLVM"] = os.environ["PYSTACHY_LLVM"]
            with tempfile.TemporaryDirectory(prefix="cache-", dir=output) as cache:
                env["PYSTACHY_CACHE"] = cache
                start = time.monotonic()
                try:
                    make_bootstrap(root, env, log)
                finally:
                    report["make_seconds"] = round(time.monotonic() - start, 3)
            witnesses = {}
            for prefix, expected in (("stage", files["stage1.ll"]), ("rt", files["rt1.ll"])):
                for index in (1, 2, 3):
                    name = f"{prefix}{index}.ll"
                    data = bundle.read_file(root / "build" / name)
                    if data != expected:
                        raise ValueError(f"O1 bootstrap witness differs from verified O2: {name}")
                    witnesses[name] = bundle.digest(data)
            installed = bundle.read_file(root / "pystachy")
            if not installed or installed != bundle.read_file(root / "build/pystachy2"):
                raise ValueError("installed compiler differs from the O1 bootstrap's final stage")
            # Recheck source/toolchain/run identity and the original bundle after Make.
            _, after = bundle.load_bundle(directory, root)
            if after["bootstrap_bundle_id"] != standard["bootstrap_bundle_id"]:
                raise ValueError("standard bootstrap bundle changed during O1 build")
            if bundle.read_file(root / "build/verification.json") != producer_report:
                raise ValueError("standard verification report changed during O1 build")
            report.update(result="pass", witnesses=witnesses,
                          final_compiler_sha256=bundle.digest(installed),
                          standard_final_compiler_sha256=bundle.digest(files["pystachy2"]),
                          final_compiler_bytes_identical=installed == files["pystachy2"])
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            report["error"] = str(exc)
            raise
        finally:
            bundle.write_file(output / "report.json", bundle.canonical(report) + b"\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args(argv)
    try:
        report = qualify(args.bundle)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"bootstrap tier: {exc}; see build/bootstrap-tier/", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
