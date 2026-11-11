"""Reproduce the rejected global-static(matchbind) idea without source edits.

Usage: python audit_static_capture_probe.py REPO original|patched SOURCE OUT.ll
This emits hosted IR only. Run each variant in its own process.
"""
import os
from pathlib import Path
import sys


repo = Path(sys.argv[1]).resolve()
variant = sys.argv[2]
source = str(Path(sys.argv[3]).resolve())
output = str(Path(sys.argv[4]).resolve())
if variant not in ("original", "patched"):
    raise SystemExit("variant must be original or patched")
os.chdir(repo)
os.environ["PYSTACHY_HOME"] = str(repo)
sys.path.insert(0, str(repo))
import pystachy  # noqa: E402
from src.pystachy_compiler.gen import Gen  # noqa: E402

if variant == "patched":
    old_static = Gen.static
    old_reads = Gen.static_reads

    def static(self, node):
        return 1 if node.kind == "matchbind" else old_static(self, node)

    def static_reads(self, node):
        if node.kind == "matchbind":
            self.expr(node.kids[0], "")
        else:
            old_reads(self, node)

    Gen.static = static
    Gen.static_reads = static_reads

sys.argv = ["pystachy.py", "ir", source, "-o", output]
pystachy.main()
