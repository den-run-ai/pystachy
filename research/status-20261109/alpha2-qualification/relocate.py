#!/usr/bin/env python3
"""Scratch same-path replay for #527, with a permanent populated home.

No directory is renamed. Immutable, independent old/new snapshots provide each
compiler binary and the exact files copied into one permanent PYSTACHY_HOME.
The unchanged irsame oracle compares outputs; this script audits home identity.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent
NAMES = ("pystachy", "lib", "runtime.c", "runtime.py", "VERSION", "ryu", "mpz", "pyext.c", "pyembed.c")


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def inventory(home, selected=None):
    paths = []
    if selected is None:
        paths = sorted(home.rglob("*"))
    else:
        for name in selected:
            top = home / name
            if not top.exists():
                raise RuntimeError(f"missing home input: {top}")
            paths.extend([top] + (sorted(top.rglob("*")) if top.is_dir() else []))
    rows = {}
    for path in paths:
        info = path.lstat()
        relative = str(path.relative_to(home))
        if stat.S_ISREG(info.st_mode):
            rows[relative] = {"kind": "file", "mode": stat.S_IMODE(info.st_mode), "size": info.st_size, "sha256": digest(path)}
        elif stat.S_ISDIR(info.st_mode):
            rows[relative] = {"kind": "directory", "mode": stat.S_IMODE(info.st_mode)}
        else:
            raise RuntimeError(f"unsupported symlink or special home input: {path}")
    return rows


def save(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def manifest_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def setup(old, new):
    if (ROOT / "config.json").exists() or (ROOT / "snapshots").exists():
        raise RuntimeError("setup already exists; use a fresh harness directory")
    config = {"issue": "https://github.com/den-run-ai/pystachy/issues/527", "homes": {}}
    for variant, source in (("old", Path(old).resolve()), ("new", Path(new).resolve())):
        before = inventory(source, NAMES)
        target = ROOT / "snapshots" / variant
        target.mkdir(parents=True)
        for name in NAMES:
            original = source / name
            if original.is_dir():
                shutil.copytree(original, target / name, copy_function=shutil.copy2)
            else:
                shutil.copy2(original, target / name)
        if inventory(source, NAMES) != before or inventory(target) != before:
            raise RuntimeError(f"source changed while snapshotting {variant}")
        identity = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        status = subprocess.check_output(["git", "-C", str(source), "status", "--porcelain", "--untracked-files=all", "--", *NAMES], text=True)
        manifest = ROOT / f"{variant}-manifest.json"
        save(manifest, before)
        config["homes"][variant] = {"source": str(source), "commit": identity, "home_status": status,
                                    "compiler_sha256": before["pystachy"]["sha256"], "manifest_sha256": digest(manifest)}
        (ROOT / variant).symlink_to("relocate.py")
    (ROOT / "active").mkdir()
    save(ROOT / "config.json", config)
    print(json.dumps(config, indent=2))


def manifests():
    config = json.loads((ROOT / "config.json").read_text())
    result = {}
    for variant in ("old", "new"):
        path = ROOT / f"{variant}-manifest.json"
        if digest(path) != config["homes"][variant]["manifest_sha256"]:
            raise RuntimeError(f"manifest changed: {variant}")
        result[variant] = json.loads(path.read_text())
    return config, result


def active_manifest(manifest):
    return {name: row for name, row in manifest.items() if name != "pystachy"}


def populate(variant, expected, all_manifests):
    active = ROOT / "active"
    current = inventory(active)
    state_path = ROOT / "active-state.json"
    if state_path.exists():
        prior = json.loads(state_path.read_text())
        prior_manifest = active_manifest(all_manifests[prior["variant"]])
        if current != prior_manifest or prior["manifest"] != manifest_digest(prior_manifest):
            raise RuntimeError("active home changed between compiler invocations")
    elif current:
        raise RuntimeError("nonempty active home has no ownership state")
    owned = set().union(*(active_manifest(m) for m in all_manifests.values()))
    unexpected = set(current) - owned
    if unexpected:
        raise RuntimeError(f"unowned entries in active home; refusing to remove them: {sorted(unexpected)}")
    # Remove only obsolete manifest-owned entries, with children first. No
    # recursive deletion and no renames: every directory stays at a fixed path.
    remove = [name for name in current if name not in expected or current[name]["kind"] != expected[name]["kind"]]
    for name in sorted(remove, key=lambda n: (n.count("/"), n), reverse=True):
        path = active / name
        if current[name]["kind"] == "directory":
            path.rmdir()
        else:
            path.unlink()
    retained = copied = 0
    for name, row in sorted(expected.items(), key=lambda item: (item[0].count("/"), item[0])):
        path = active / name
        if row["kind"] == "directory":
            path.mkdir(exist_ok=True)
            path.chmod(row["mode"])
        elif current.get(name) == row and all(m.get(name) == row for m in all_manifests.values()) and path.exists():
            retained += 1
        else:
            shutil.copyfile(ROOT / "snapshots" / variant / name, path)
            path.chmod(row["mode"])
            copied += 1
    if inventory(active) != expected:
        raise RuntimeError(f"populated active home does not exactly match {variant}")
    save(ROOT / "active-state.json", {"variant": variant, "manifest": manifest_digest(expected)})
    return {"retained_files": retained, "copied_files": copied}


def pair_args(args):
    return args[:-1] if len(args) >= 2 and args[-2] == "-o" else args


def validate_pair(old, new, all_manifests):
    if old["variant"] != "old" or new["variant"] != "new":
        raise RuntimeError("invalid invocation order")
    for key in ("args", "cwd", "path", "active", "source_sha256"):
        if old[key] != new[key]:
            raise RuntimeError(f"pair identity mismatch: {key}")
    for row in (old, new):
        expected = all_manifests[row["variant"]]
        if row["compiler_sha256"] != expected["pystachy"]["sha256"]:
            raise RuntimeError("pair compiler identity mismatch")
        if row["home_manifest"] != manifest_digest(active_manifest(expected)):
            raise RuntimeError("pair home identity mismatch")
        if not row["post_home_verified"] or not row["post_snapshot_verified"]:
            raise RuntimeError("pair lacks post-execution integrity check")
    return any(old[key] != new[key] for key in ("status", "output_sha256"))


def append(path, row):
    with path.open("a") as target:
        target.write(json.dumps(row, sort_keys=True) + "\n")


def launch(variant, args):
    if args and args[0] not in ("ir", "rt", "check"):
        raise RuntimeError("only irsame usage, ir, rt and check calls are permitted")
    if os.environ.get("PYSTACHY_JOBS") != "1":
        raise RuntimeError("serialized harness requires explicit PYSTACHY_JOBS=1")
    with (ROOT / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if list(ROOT.glob("ERROR-*")):
            raise RuntimeError("a previous harness error invalidates this run")
        _, all_manifests = manifests()
        expected = all_manifests[variant]
        snapshot = ROOT / "snapshots" / variant
        if inventory(snapshot) != expected:
            raise RuntimeError(f"immutable snapshot changed: {variant}")
        pending = ROOT / "pending.json"
        key = {"args": pair_args(args), "cwd": os.getcwd(), "path": os.environ.get("PYSTACHY_PATH", "")}
        if variant == "old":
            if pending.exists():
                raise RuntimeError("unpaired old invocation; expected strict OLD/NEW order")
            save(pending, {"key": key})
        else:
            if not pending.exists():
                raise RuntimeError("new invocation has no matching old call")
            previous_pair = json.loads(pending.read_text())
            if previous_pair.get("key") != key or "old" not in previous_pair:
                raise RuntimeError("new invocation does not match a completed old call")
        home_manifest = active_manifest(expected)
        changes = populate(variant, home_manifest, all_manifests)
        active = ROOT / "active"
        source = Path(args[1]) if len(args) > 1 and Path(args[1]).is_file() else None
        source_before = digest(source) if source else None
        env = os.environ.copy()
        env["PYSTACHY_HOME"] = str(active)
        process = None
        previous_handlers = {}

        def interrupted(number, frame):
            raise InterruptedError(number)

        try:
            for number in (signal.SIGINT, signal.SIGTERM):
                previous_handlers[number] = signal.getsignal(number)
                if previous_handlers[number] != signal.SIG_IGN:
                    signal.signal(number, interrupted)
            # The binary is selected from its own immutable snapshot. Only its
            # home inputs use the permanent active path. Stdio/cwd are inherited.
            process = subprocess.Popen([str(snapshot / "pystachy"), *args], env=env, close_fds=False)
            result = process.wait()
        except BaseException:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            raise
        finally:
            for number, handler in previous_handlers.items():
                signal.signal(number, handler)
        if inventory(active) != home_manifest or inventory(snapshot) != expected:
            raise RuntimeError(f"home or immutable snapshot changed during {variant} execution")
        if source and digest(source) != source_before:
            raise RuntimeError("source file changed during compilation")
        output = Path(args[-1]) if len(args) >= 2 and args[-2] == "-o" else None
        row = {**key, **changes, "variant": variant, "active": str(active), "status": result,
               "compiler_sha256": expected["pystachy"]["sha256"], "home_manifest": manifest_digest(home_manifest),
               "post_home_verified": True, "post_snapshot_verified": True,
               "output_sha256": digest(output) if output is not None and output.is_file() else None,
               "source_sha256": source_before, "completed_ns": time.time_ns()}
        append(ROOT / "invocations.jsonl", row)
        if variant == "old":
            save(pending, {"key": key, "old": row})
        else:
            differs = validate_pair(previous_pair["old"], row, all_manifests)
            append(ROOT / "pairs.jsonl", {"args": key["args"], "different_output_or_status": differs, "completed_ns": time.time_ns()})
            pending.unlink()
    if result < 0:
        number = -result
        signal.signal(number, signal.SIG_DFL)
        os.kill(os.getpid(), number)
    return result


def audit():
    with (ROOT / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if list(ROOT.glob("ERROR-*")) or (ROOT / "pending.json").exists():
            raise RuntimeError("harness error or unfinished pair")
        config, all_manifests = manifests()
        for variant in ("old", "new"):
            if inventory(Path(config["homes"][variant]["source"]), NAMES) != all_manifests[variant]:
                raise RuntimeError(f"original source home changed: {variant}")
            if inventory(ROOT / "snapshots" / variant) != all_manifests[variant]:
                raise RuntimeError(f"immutable snapshot changed: {variant}")
        state = json.loads((ROOT / "active-state.json").read_text())
        expected = active_manifest(all_manifests[state["variant"]])
        if inventory(ROOT / "active") != expected or state["manifest"] != manifest_digest(expected):
            raise RuntimeError("active home mismatch at final audit")
        rows = [json.loads(line) for line in (ROOT / "invocations.jsonl").read_text().splitlines()]
        pairs = [json.loads(line) for line in (ROOT / "pairs.jsonl").read_text().splitlines()]
        if len(rows) != 2 * len(pairs):
            raise RuntimeError("invocation and per-pair audit counts differ")
        counts = {"workers": 1, "pairs": len(pairs), "ir_pairs": 0, "different_output_or_status_pairs": 0}
        for old, new, pair in zip(rows[::2], rows[1::2], pairs):
            differs = validate_pair(old, new, all_manifests)
            if pair["args"] != old["args"] or pair["different_output_or_status"] != differs:
                raise RuntimeError("per-pair audit disagrees with invocation log")
            counts["ir_pairs"] += bool(old["args"] and old["args"][0] in ("ir", "rt"))
            counts["different_output_or_status_pairs"] += differs
        save(ROOT / "audit.json", counts)
        print(json.dumps(counts, indent=2))
        return int(counts["different_output_or_status_pairs"] != 0)


if __name__ == "__main__":
    mode = Path(sys.argv[0]).name
    try:
        if mode in ("old", "new"):
            code = launch(mode, sys.argv[1:])
        elif sys.argv[1:2] == ["setup"] and len(sys.argv) == 4:
            setup(sys.argv[2], sys.argv[3])
            code = 0
        elif sys.argv[1:] == ["audit"]:
            code = audit()
        else:
            raise RuntimeError("usage: relocate.py setup OLD_HOME NEW_HOME | audit")
    except BaseException as error:
        message = f"populated-home harness {mode} failure: {type(error).__name__}: {error}"
        (ROOT / f"ERROR-{time.time_ns()}-{uuid.uuid4().hex}").write_text(message + "\n")
        print(message, file=sys.stderr)
        code = 125
    raise SystemExit(code)
