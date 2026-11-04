"""Verify an imported pystachy_json_repair extension against the maintained corpus."""
import argparse
from contextlib import redirect_stdout
from importlib.machinery import ExtensionFileLoader
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_root", nargs="?", type=Path,
                        help="directory containing pystachy_json_repair (default: installed package)")
    args = parser.parse_args()
    if args.package_root:
        sys.path.insert(0, str(args.package_root.resolve()))
    import pystachy_json_repair as companion

    extension = companion._native
    if not isinstance(extension.__spec__.loader, ExtensionFileLoader):
        parser.error(f"expected a compiled extension, loaded {extension.__file__}")
    if args.package_root and Path(companion.__file__).resolve().parent != (
            args.package_root.resolve() / "pystachy_json_repair"):
        parser.error(f"package was loaded from outside the requested directory: {companion.__file__}")
    print(f"Checking {extension.__file__}", flush=True)

    class NonIndexableString(str):
        def __getitem__(self, index):
            raise AssertionError("The CPython decoder does not index a str subclass")

    if companion.loads(NonIndexableString('{"ok":true}')) != {"ok": True}:
        raise AssertionError("valid str subclass did not use the CPython decoder")

    suite = Path(__file__).resolve().parent
    checker = suite.parents[2] / "tools/json_repair_parity.py"
    with tempfile.TemporaryDirectory() as tmp:
        inputs, output = Path(tmp) / "inputs.jsonl", Path(tmp) / "output.jsonl"
        subprocess.run([sys.executable, checker, "--write-inputs", inputs], check=True)
        # Run the same public API calls as the JIT, AOT and pristine CPython
        # replays, selecting the already imported companion for this process.
        sys.modules["json_repair"] = companion
        sys.argv = [str(suite / "replay.py"), str(inputs)]
        with output.open("w", encoding="utf-8") as capture, redirect_stdout(capture):
            runpy.run_path(sys.argv[0], run_name="__main__")
        subprocess.run([sys.executable, checker, output], check=True)


if __name__ == "__main__":
    main()
