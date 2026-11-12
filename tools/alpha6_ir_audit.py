#!/usr/bin/env python3
"""Temporary, branch-only retained IR comparison; never a release gate."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import platform
import queue
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import time

SOURCES = {
    "old": ("6e02b36b404cd295058967ea48860c2941ce59fc",
            "ce2d89b961f0e29945b111f39f450b282524d5c4"),
    "new": ("0ed84b74431058b8ad063d1580d3a5782e1acc6e",
            "3e062cbe5f67c263192cc6ec596dad844b208064"),
}
EXPECTED = 4451
SELF = Path(__file__).resolve()
STOP = threading.Event()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    temporary.replace(path)


def command(argv, cwd=None):
    return subprocess.run(argv, cwd=cwd, check=True, capture_output=True,
                          timeout=60).stdout


def context():
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("this diagnostic requires Linux x86_64")
    if sys.version_info[:3] != (3, 13, 16):
        raise ValueError("CPython 3.13.16 is required")
    if (os.environ.get("GITHUB_REPOSITORY") != "den-run-ai/pystachy"
            or os.environ.get("GITHUB_EVENT_NAME") != "push"
            or os.environ.get("GITHUB_REF") != "refs/heads/codex/alpha6-ir-diagnostic"):
        raise ValueError("unexpected repository, event or diagnostic branch")
    values = {key: os.environ[key] for key in
              ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA", "GITHUB_WORKFLOW_REF")}
    if not values["GITHUB_RUN_ID"].isdigit() or not values["GITHUB_RUN_ATTEMPT"].isdigit():
        raise ValueError("missing run or attempt identity")
    if command(["git", "rev-parse", "HEAD"], SELF.parent.parent).decode().strip() != values["GITHUB_SHA"]:
        raise ValueError("diagnostic checkout is not this workflow's push commit")
    values["harness_sha256"] = digest(SELF)
    return values


def source_check(side, root):
    commit, tree = SOURCES[side]
    for expression, expected in (("HEAD", commit), ("HEAD^{tree}", tree)):
        if command(["git", "rev-parse", expression], root).decode().strip() != expected:
            raise ValueError(f"{side}: unexpected {expression}")
    if command(["git", "status", "--porcelain", "--untracked-files=all"], root):
        raise ValueError(f"{side}: checkout is dirty")
    if (root / ".python-version").read_text().strip() != "3.13.16":
        raise ValueError(f"{side}: unexpected Python pin")
    return {"commit": commit, "tree": tree}


def validated(side, root, bundle):
    """Call the source checkout's unchanged validator; never substitute another one."""
    source = source_check(side, root)
    helper = (
        "import hashlib,json,sys; from pathlib import Path; "
        "root=Path(sys.argv[1]); sys.path.insert(0,str(root/'tools')); "
        "import verification_bootstrap as vb; "
        "files,fields=vb.load_bundle(Path(sys.argv[2]),root); "
        "print(json.dumps({'identity':vb.identity(root),'fields':fields,"
        "'compiler_sha256':hashlib.sha256(files['pystachy2']).hexdigest()}))"
    )
    result = json.loads(command([sys.executable, "-I", "-c", helper,
                                 str(root), str(bundle)], root))
    if any("version 18." not in version for version in result["identity"]["tools"].values()):
        raise ValueError("LLVM 18 is required")
    result.update(source=source, manifest_sha256=digest(bundle / "manifest.json"),
                  side=side, context=context())
    return result


def seal(args):
    receipt = validated(args.side, args.root, args.bundle)
    write_json(args.bundle.parent / "receipt.json", receipt)
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        for name in ("manifest_sha256", "compiler_sha256"):
            print(f"{name}={receipt[name]}", file=output)
    print(json.dumps(receipt, sort_keys=True))


def restore(args):
    receipt = json.loads((args.bundle.parent / "receipt.json").read_text())
    current = validated(args.side, args.root, args.bundle)
    if receipt != current:
        raise ValueError("producer receipt differs from this source/run/attempt/toolchain")
    if (receipt["manifest_sha256"] != args.manifest_sha256
            or receipt["compiler_sha256"] != args.compiler_sha256):
        raise ValueError("bundle does not match producer job outputs")
    command([sys.executable, str(args.root / "tools/verification_bootstrap.py"),
             "restore", str(args.bundle)], args.root)
    if digest(args.root / "build/verify/pystachy2") != args.compiler_sha256:
        raise ValueError("restored compiler digest differs")
    print(json.dumps(receipt, sort_keys=True))


def file_info(path):
    if not path.exists():
        return {"exists": False}
    return {"exists": True, "bytes": path.stat().st_size, "sha256": digest(path)}


def run_process(argv, cwd, env, log, deadline, limit):
    """Retain combined stdout/stderr in original emission order and reap owned groups."""
    started = time.monotonic()
    record = {"argv": [str(a) for a in argv], "cwd": str(cwd),
              "returncode": None, "timeout": False, "interrupted": False,
              "launch_error": None, "combined_streams": True}
    process = None
    with log.open("wb") as output:
        if STOP.is_set() or started >= deadline:
            record["interrupted"] = True
        else:
            try:
                process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=output,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                end = min(deadline, started + limit)
                while process.poll() is None:
                    if STOP.is_set() or time.monotonic() >= end:
                        record["timeout"] = time.monotonic() >= end
                        record["interrupted"] = STOP.is_set()
                        try:
                            os.killpg(process.pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            try:
                                os.killpg(process.pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                            process.wait(timeout=5)
                        break
                    try:
                        process.wait(timeout=0.1)
                    except subprocess.TimeoutExpired:
                        pass
                record["returncode"] = process.wait(timeout=5)
            except (OSError, subprocess.SubprocessError) as exc:
                record["launch_error"] = str(exc)
                if process is not None and process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=5)
    record["seconds"] = round(time.monotonic() - started, 6)
    record["log"] = file_info(log)
    return record


def clean_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    for key in ("LD_PRELOAD", "PYTHONPATH", "PYTHONHOME"):
        env.pop(key, None)
    env.update(PYSTACHY_LLVM="/usr/lib/llvm-18/bin", PYSTACHY_JOBS="2",
               PYSTACHY_IRCHECK="1", PYSTACHY_PROGRAM_CACHE="0",
               LC_ALL="C", TZ="UTC")
    return env


def completed(record):
    return (record["returncode"] in (0, 1) and not record["timeout"]
            and not record["interrupted"] and record["launch_error"] is None)


def usage_completed(record):
    # driver.main() deliberately exits 2 after printing no-argument usage.
    return (record["returncode"] == 2 and not record["timeout"]
            and not record["interrupted"] and record["launch_error"] is None)


def inventory(root):
    corpus = command(["sh", "-c", ". tests/corpus.sh; corpus"], root).decode().splitlines()
    errors = [p for p in corpus if p.startswith("tests/errors/")]
    cases = ["pystachy.py", "runtime.py"]
    cases += [p for p in corpus if p not in errors]
    for pattern in ("bench/*.py", "bench/pyperformance/*.py", "tests/ir/*.py"):
        cases += [p.relative_to(root).as_posix() for p in sorted(root.glob(pattern)) if p.is_file()]
    cases += errors
    if len(cases) != EXPECTED or len(set(cases)) != EXPECTED:
        raise ValueError(f"expected exactly {EXPECTED} distinct cases, got {len(cases)}")
    entries = []
    for index, name in enumerate(cases):
        path = root / name
        if not path.is_file():
            raise ValueError(f"missing corpus input: {name}")
        entry = {"index": index, "path": name, "source": file_info(path)}
        if path.is_symlink():
            entry["symlink"] = os.readlink(path)
            entry["resolved_path"] = str(path.resolve())
        sidecar = path.with_suffix(".path")
        if sidecar.exists():
            entry["path_sidecar"] = file_info(sidecar)
        entries.append(entry)
    return entries


def audit(args):
    ctx = context()
    old, new, output = args.old.resolve(), args.new.resolve(), args.output.resolve()
    if old == new or any(output.is_relative_to(p) for p in (old, new, SELF.parent.parent)):
        raise ValueError("source roots and evidence directory must be separate")
    output.mkdir(parents=True, exist_ok=False)
    summary = {"complete": False, "expected": EXPECTED, "release_qualification": "not_evaluated",
               "context": ctx}
    write_json(output / "summary.json", summary)
    before = {}
    roots = {"old": old, "new": new}
    for side, root in roots.items():
        bundle = args.bundles.resolve() / side / "bundle"
        receipt = json.loads((bundle.parent / "receipt.json").read_text())
        before[side] = validated(side, root, bundle)
        if before[side] != receipt or digest(root / "build/verify/pystachy2") != receipt["compiler_sha256"]:
            raise ValueError(f"{side}: source or restored compiler changed")
    write_json(output / "inputs-before.json", before)
    entries = inventory(new)
    write_json(output / "inventory.json", entries)
    # Execute exactly the existing functions, including conservative quoted-path handling.
    original = (new / "tools/irsame.sh").read_text()
    if original != (old / "tools/irsame.sh").read_text():
        raise ValueError("normalization implementation differs between source revisions")
    start = original.index("quoted_library_path() (")
    end = original.index("\nRT=0 ", start)
    normalizer = output / "normalize.sh"
    normalizer.write_text("#!/bin/sh\n" + original[start:end]
                          + '\nnormalize_messages "$1" "$2"\n')
    write_json(output / "normalization.json",
               {"source": "tools/irsame.sh", "source_sha256": digest(new / "tools/irsame.sh"),
                "extracted_sha256": digest(normalizer), "ir_normalized": False})
    deadline = time.monotonic() + 600
    capabilities = {}
    for side, root in roots.items():
        env = dict(clean_env(), PYSTACHY_HOME=str(root), PYSTACHY_PATH="")
        usage = output / (side + "-usage.msg")
        record = run_process([str(root / "build/verify/pystachy2")], new, env,
                             usage, deadline, 5)
        record["runtime_mode_advertised"] = b"pystachy rt " in usage.read_bytes()
        capabilities[side] = record
        write_json(output / "capabilities.json", capabilities)
        if not usage_completed(record) or not record["runtime_mode_advertised"]:
            raise ValueError(f"{side}: compiler does not advertise runtime mode")
    work = queue.Queue()
    for entry in entries:
        work.put(entry)
    finished = []
    lock = threading.Lock()
    failures = []

    def worker():
        while not STOP.is_set() and time.monotonic() < deadline:
            try:
                entry = work.get_nowait()
            except queue.Empty:
                return
            directory = output / "cases" / f"{entry['index']:05d}"
            directory.mkdir(parents=True)
            result = {"input": entry, "runs": {
                side: {"valid": False, "accepted": False, "returncode": None,
                       "not_run": "setup_or_interruption"} for side in roots},
                "setup": None, "normalization": {}, "error": None}
            try:
                name = entry["path"]
                env = clean_env()
                module_path = ""
                if (new / name).with_suffix(".path").exists():
                    setup = run_process(["sh", "-c",
                                         'sh tests/prepare_path.sh "$1" "$2" > "$3"',
                                         "prepare-path", name, str(directory), str(directory / "path.txt")],
                                        new, env, directory / "setup.msg", deadline, 10)
                    result["setup"] = setup
                    if not completed(setup) or setup["returncode"] != 0:
                        raise ValueError("import-path setup failed")
                    module_path = (directory / "path.txt").read_text().rstrip("\n")
                    result["prepared_path"] = module_path
                mode = "rt" if name == "runtime.py" or Path(name).name.startswith("rtmode_") else "ir"
                for side, root in roots.items():
                    side_env = dict(env, PYSTACHY_HOME=str(root), PYSTACHY_PATH=module_path,
                                    PYSTACHY_CACHE=str(output / "cache" / side))
                    ir = directory / (side + ".ll")
                    record = run_process([str(root / "build/verify/pystachy2"),
                                          mode, name, "-o", str(ir)],
                                         new, side_env, directory / (side + ".msg"), deadline, 90)
                    record["ir"] = file_info(ir)
                    record["accepted"] = (record["returncode"] == 0 and record["ir"]["exists"]
                                          and record["ir"].get("bytes", 0) > 0)
                    record["valid"] = (completed(record) and
                                       (record["returncode"] != 0 or record["accepted"])
                                       and b"error: internal error" not in
                                       (directory / (side + ".msg")).read_bytes())
                    result["runs"][side] = record
                raw_equal = result["runs"]["old"]["log"] == result["runs"]["new"]["log"]
                result["raw_messages_equal"] = raw_equal
                for side, root in roots.items():
                    raw = directory / (side + ".msg")
                    normalized = directory / (side + ".normal.msg")
                    if raw_equal:
                        shutil.copyfile(raw, normalized)
                    else:
                        record = run_process(["sh", str(normalizer), str(root / "lib") + "/", str(raw)],
                                             new, env, normalized, deadline, 10)
                        result["normalization"][side] = record
                        if not completed(record) or record["returncode"] != 0:
                            raise ValueError("diagnostic normalization failed")
                a, b = result["runs"]["old"], result["runs"]["new"]
                result["new_rejection"] = a["accepted"] and b["valid"] and b["returncode"] == 1
                result["differences"] = [
                    key for key, different in (
                        ("status", a["returncode"] != b["returncode"]),
                        ("ir", a["ir"] != b["ir"]),
                        ("messages", digest(directory / "old.normal.msg") !=
                         digest(directory / "new.normal.msg")),
                    ) if different
                ]
                if a["ir"]["exists"] and b["ir"]["exists"] and a["ir"] != b["ir"]:
                    difference = run_process(["diff", "-u", str(directory / "old.ll"),
                                              str(directory / "new.ll")],
                                             new, env, directory / "ir.diff", deadline, 20)
                    result["ir_diff_process"] = difference
                    if not completed(difference) or difference["returncode"] not in (0, 1):
                        raise ValueError("IR difference retention failed")
                    with (directory / "ir.diff").open() as diff_file:
                        result["ir_diff_preview"] = [line.rstrip("\n") for _, line
                                                     in zip(range(40), diff_file)]
                if digest(directory / "old.normal.msg") != digest(directory / "new.normal.msg"):
                    result["message_preview"] = {
                        side: (directory / (side + ".normal.msg")).read_text(errors="replace")[:4000]
                        for side in roots
                    }
            except Exception as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
            write_json(directory / "result.json", result)
            with lock:
                finished.append(result)
                if len(finished) % 100 == 0:
                    print(f"{len(finished)}/{EXPECTED} cases retained", flush=True)

    def stop(_signal, _frame):
        STOP.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                failures.append(f"{type(exc).__name__}: {exc}")
                STOP.set()
    after = {}
    for side, root in roots.items():
        try:
            after[side] = validated(side, root, args.bundles.resolve() / side / "bundle")
            if after[side] != before[side] or digest(root / "build/verify/pystachy2") != before[side]["compiler_sha256"]:
                failures.append(f"{side}: source or compiler changed during audit")
        except Exception as exc:
            failures.append(f"{side}: final identity check: {exc}")
    write_json(output / "inputs-after.json", after)
    finished.sort(key=lambda result: result["input"]["index"])
    complete = (len(finished) == EXPECTED
                and {r["input"]["index"] for r in finished} == set(range(EXPECTED))
                and not failures and all(
        result["error"] is None and set(result["runs"]) == {"old", "new"}
        and all(run["valid"] for run in result["runs"].values()) for result in finished))
    diffs = [{"path": r["input"]["path"], "differences": r.get("differences", []),
              "new_rejection": r.get("new_rejection", False),
              "record": f"cases/{r['input']['index']:05d}/result.json",
              "ir_preview": r.get("ir_diff_preview"), "message_preview": r.get("message_preview") }
             for r in finished if r.get("differences") or r["error"]
             or not all(x.get("valid", False) for x in r["runs"].values())]
    raw_message_differences = [
        {"path": r["input"]["path"], "record": f"cases/{r['input']['index']:05d}/result.json"}
        for r in finished if r.get("raw_messages_equal") is False
    ]
    rejected = [r["input"]["path"] for r in finished if r.get("new_rejection")]
    seen = {r["input"]["index"] for r in finished}
    summary.update(complete=complete, completed_cases=len(finished),
                   compiler_records=sum(run.get("returncode") is not None
                                        for r in finished for run in r["runs"].values()),
                   terminal_records=sum(len(r["runs"]) for r in finished),
                   missing=[e["path"] for e in entries if e["index"] not in seen],
                   failures=failures, differences=diffs, new_rejections=rejected,
                   raw_message_differences=raw_message_differences,
                   raw_message_difference_count=len(raw_message_differences),
                   difference_review_required=bool(diffs),
                   status=("incomplete" if not complete else "new_rejections" if rejected
                           else "complete_with_differences" if diffs
                           else "normalized_oracle_identical" if raw_message_differences
                           else "raw_identical"),
                   inventory_sha256=digest(output / "inventory.json"))
    write_json(output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True), flush=True)
    return 0 if complete and not rejected else 1


def self_test():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        def run(code, limit=5):
            return run_process([sys.executable, "-c", code], root, os.environ.copy(),
                               root / "log", time.monotonic() + 10, limit)
        assert completed(run("print('ok')"))
        assert completed(run("raise SystemExit(1)"))
        usage = run("raise SystemExit(2)")
        assert not completed(usage)
        assert usage_completed(usage)
        assert not completed(run("import os,signal; os.kill(os.getpid(),signal.SIGTERM)"))
        result = run("import time; time.sleep(10)", 0.1)
        assert result["timeout"] and not completed(result)
        assert not file_info(root / "missing")["exists"]
    print("subprocess success/rejection/abnormal/signal/timeout controls passed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("self-test")
    for action in ("check", "seal", "restore"):
        child = sub.add_parser(action)
        child.add_argument("--side", choices=SOURCES, required=True)
        child.add_argument("--root", type=Path, required=True)
        if action != "check":
            child.add_argument("--bundle", type=Path, required=True)
        if action == "restore":
            child.add_argument("--manifest-sha256", required=True)
            child.add_argument("--compiler-sha256", required=True)
    child = sub.add_parser("audit")
    for name in ("old", "new", "bundles", "output"):
        child.add_argument("--" + name, type=Path, required=True)
    child = sub.add_parser("pack")
    child.add_argument("--directory", type=Path, required=True)
    child.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "self-test":
        self_test()
    elif args.action == "check":
        context()
        print(json.dumps(source_check(args.side, args.root.resolve()), sort_keys=True))
    elif args.action == "seal":
        seal(args)
    elif args.action == "restore":
        restore(args)
    elif args.action == "audit":
        return audit(args)
    elif args.action == "pack":
        temporary = args.archive.with_name(args.archive.name + ".tmp")
        with tarfile.open(temporary, "w:gz", compresslevel=1) as archive:
            archive.add(args.directory, arcname="alpha6-ir-evidence", recursive=True)
        temporary.replace(args.archive)
        print(digest(args.archive))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
