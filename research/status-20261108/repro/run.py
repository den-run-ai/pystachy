"""Re-run the 2026-11-08 status-check reproducers against a Pystachy build.

Usage, from the checkout root after `make`:

    python3 -I research/status-20261108/repro/run.py [--pystachy ./pystachy]

Each line reports REPRODUCES or OK by comparing Pystachy with CPython (or a
cached Pystachy launch with an uncached one); control paths should print OK.
Caches, temporary files and AOT executables live in a private temporary
directory that is removed afterwards. Exit status 1 means something reproduces.
"""

import argparse
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
RESULTS: list[bool] = []


def env_for(root: pathlib.Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("PYSTACHY_") or k == "PYSTACHY_LLVM"}
    env["PYSTACHY_CACHE"] = str(root / "cache")
    env["TMPDIR"] = str(root / "tmp")
    env.update(extra)
    return env


def run(cmd: list[str], env: dict[str, str], closed_stdin: bool = False,
        cwd: pathlib.Path | None = None) -> tuple[int, str]:
    if closed_stdin:
        cmd = ["sh", "-c", 'exec "$@" 0<&-', "sh", *cmd]
    p = subprocess.run(cmd, env=env, cwd=cwd, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=600)
    return p.returncode, (p.stdout + p.stderr).strip()


def last(text: str) -> str:
    lines = [x for x in text.splitlines() if "program cache:" not in x]
    return lines[-1] if lines else ""


def report(name: str, reproduces: bool, detail: str) -> None:
    RESULTS.append(reproduces)
    print(f"{'REPRODUCES' if reproduces else 'OK        '}  {name}: {detail}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pystachy", default=str(HERE.parents[2] / "pystachy"))
    ap.add_argument("--python", default=shutil.which("python3.13") or sys.executable)
    ap.add_argument("--keep", action="store_true", help="keep the temporary directory")
    a = ap.parse_args()
    pys = str(pathlib.Path(a.pystachy).resolve())
    hosted = [a.python, "-E", "-B", str(pathlib.Path(pys).parent / "pystachy.py"), "run"]
    root = pathlib.Path(tempfile.mkdtemp(prefix="pystachy-status-"))
    (root / "tmp").mkdir()
    base = env_for(root)
    nocache = env_for(root, PYSTACHY_PROGRAM_CACHE="0")
    mcjit = env_for(root, PYSTACHY_PROGRAM_CACHE="0", PYSTACHY_JIT_CODEGEN="0")
    try:
        def aot(prog: pathlib.Path, closed_stdin: bool = False) -> tuple[int, str]:
            exe = root / (prog.stem + ".bin")
            rc, out = run([pys, "build", str(prog), "-o", str(exe)], nocache)
            return run([str(exe)], base, closed_stdin) if rc == 0 else (rc, out)

        # 1. zip() with a dynamic-Any iterator reads list items after __next__.
        for name in ["zip_dynany.py", "zip_dynany_clear.py"]:
            prog = HERE / name
            ref = run([a.python, "-I", str(prog)], base)
            jit = run([pys, "run", str(prog)], nocache)
            built = aot(prog)
            bad = [m for m, r in [("JIT", jit), ("AOT", built)] if (r[0], last(r[1])) != (ref[0], last(ref[1]))]
            report(f"zip-dynamic-any {name}", bool(bad),
                   f"CPython {last(ref[1])!r}; JIT {last(jit[1])!r}; AOT {last(built[1])!r}")

        # 2. MCJIT: lli's jitdump file takes a closed stdin, and stays behind.
        rc, out = run([pys, "run", str(HERE / "stdin_read.py")], mcjit, closed_stdin=True)
        report("mcjit-closed-stdin", rc == 0 and "read 0" in out, f"exit {rc}, {last(out)!r}")
        dumps = list((root / "tmp").rglob("jit-*.dump"))
        report("mcjit-dump-leftover", len(dumps) > 0, f"{len(dumps)} jitdump file(s) left in TMPDIR")

        # 3. An extensionless file satisfies `import name` as a namespace package.
        ext = root / "extless"
        shutil.copytree(HERE / "extless", ext)
        ref = run([a.python, "-E", "-s", "-B", "main.py"], base, cwd=ext)
        jit = run([pys, "run", "main.py"], nocache, cwd=ext)
        report("extensionless-import", last(jit[1]) != last(ref[1]),
               f"CPython {last(ref[1])!r}; JIT {last(jit[1])!r}")

        # 4. lli launches leak the JIT input files on the lowest free descriptors.
        prog = HERE / "fd3.py"
        ref = last(run([a.python, "-I", str(prog)], base)[1])
        for mode, cmd, env in [("native, cache off", [pys, "run"], nocache),
                               ("hosted (PyPI path)", hosted, base),
                               ("control: native, cached", [pys, "run"], base)]:
            got = last(run(cmd + [str(prog)], env)[1])
            report(f"jit-input-fd-leak ({mode})", got != ref, f"CPython {ref!r}; Pystachy {got!r}")

        # 5. Program-cache key: PYSTACHY_DEBUG_LINES and empty settings.
        ck = root / "cachekey"
        ck.mkdir()
        shutil.copy(HERE / "cache_prog.py", ck / "prog.py")
        keyed = env_for(ck, PYSTACHY_PROGRAM_CACHE_TRACE="1")
        (ck / "tmp").mkdir()
        rc, out = run([pys, "run", str(ck / "prog.py")], keyed)
        if "stored" not in out and "hit" not in out:
            print(f"SKIPPED     program-cache-key: cache not used here ({out.splitlines()[:1]})")
        else:
            rc, out = run([pys, "run", str(ck / "prog.py")], dict(keyed, PYSTACHY_DEBUG_LINES="1"))
            report("cache-key-debug-lines", "program cache: hit" in out,
                   "PYSTACHY_DEBUG_LINES=1 launch was " + ("a hit" if "hit" in out else "not a hit"))
            hit = run([pys, "run", str(ck / "prog.py")], dict(keyed, PYSTACHY_JIT_INLINE=""))
            plain = run([pys, "run", str(ck / "prog.py")], dict(keyed, PYSTACHY_JIT_INLINE="", PYSTACHY_PROGRAM_CACHE="0"))
            report("cache-key-empty-jit-inline", hit[0] != plain[0],
                   f"cached exit {hit[0]}, uncached exit {plain[0]}")

        # 6. input() with stdin closed.
        prog = HERE / "input_closed.py"
        ref = last(run([a.python, "-I", str(prog)], base, closed_stdin=True)[1])
        jit = last(run([pys, "run", str(prog)], nocache, closed_stdin=True)[1])
        built = last(aot(prog, closed_stdin=True)[1])
        report("input-closed-stdin", (jit, built) != (ref, ref),
               f"CPython {ref!r}; JIT {jit!r}; AOT {built!r}")

        # 7. #50: an inherited SIG_IGN for SIGINT.
        prog = HERE / "sigint.py"
        old = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            ref = last(run([a.python, "-I", str(prog)], base)[1])
            for mode, cmd, env in [("native, cache off", [pys, "run"], nocache),
                                   ("hosted (PyPI path)", hosted, base),
                                   ("MCJIT", [pys, "run"], mcjit),
                                   ("control: native, cached", [pys, "run"], base)]:
                got = last(run(cmd + [str(prog)], env)[1])
                report(f"sigint-ignored #50 ({mode})", got != ref, f"CPython {ref!r}; Pystachy {got!r}")
            got = last(aot(prog)[1])
            report("sigint-ignored #50 (control: AOT)", got != ref, f"CPython {ref!r}; Pystachy {got!r}")
        finally:
            signal.signal(signal.SIGINT, old)
    finally:
        if a.keep:
            print("kept", root)
        else:
            shutil.rmtree(root, ignore_errors=True)
    print(f"{sum(RESULTS)} of {len(RESULTS)} checks reproduce")
    return 1 if any(RESULTS) else 0


if __name__ == "__main__":
    sys.exit(main())
