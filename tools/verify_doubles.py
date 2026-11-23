"""The bootstrap interface that the verification harness tests' compiler doubles share.

tests/verify.sh and the Makefile build each stage with `build pystachy.py -o EXE` and check the
fixed points with `ir pystachy.py -o OUT` and `rt runtime.py -o OUT`. Stage 3 runs through
tools/self_compile_once.sh, which requires the compiler to report one type-inference attempt
(`program.attempt` under PYSTACHY_TIMING=1). Each double (test_verify_contracts, test_verify_gc,
test_verify_shards, test_bootstrap_tier) includes STAGE in its source and calls stage() for these
commands, and copy_scripts() puts the repository scripts the bootstrap runs in its tree, so a
change to that interface is made here once instead of in every double.
"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
# the scripts tests/verify.sh's groups run from the repository before their own doubles take over
SCRIPTS = ("tests/verify.sh", "tests/corpus.sh", "tools/irsame.sh", "tools/self_compile_once.sh")
# (the Makefile's bootstrap runs only this one)
MAKE_SCRIPTS = ("tools/self_compile_once.sh",)

STAGE = '''
def stage(args, attempts=1, text="fixed point\\n"):
    """ARGS: build, ir or rt FILE -o OUT. build copies this double as the compiler; ir reports
    ATTEMPTS type-inference attempts under PYSTACHY_TIMING=1; ir and rt write TEXT to OUT."""
    import os
    from pathlib import Path
    import shutil
    import sys
    output = Path(args[args.index("-o") + 1])
    if args[0] == "build":
        shutil.copy(__file__, output)
        output.chmod(0o755)
        return
    if args[0] == "ir" and os.environ.get("PYSTACHY_TIMING") == "1":
        print("pystachy-timing\\tprogram.attempt\\t0.5\\n" * attempts, end="", file=sys.stderr)
    output.write_text(text)
'''


def copy_scripts(root: Path, names: tuple[str, ...] = SCRIPTS) -> None:
    """Copy NAMES from the repository into ROOT, a double's tree, keeping their modes."""
    for name in names:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / name, root / name)
