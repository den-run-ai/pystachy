"""Bind an unchanged native build to the two-line guard-oracle correction."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

repo, origin_path, destination = map(lambda value: Path(value).resolve(), sys.argv[1:4])
digest = lambda data: hashlib.sha256(data).hexdigest()
file_digest = lambda path: digest(Path(path).read_bytes())
git_bytes = lambda *args: subprocess.check_output(["git", *args], cwd=repo)
git = lambda *args: git_bytes(*args).decode().strip()
origin = json.loads(origin_path.read_text())
assert origin["status"] == "complete" and origin["exit_code"] == 0
assert origin["fresh_local_build"] and origin["source_identity_stable"]
assert origin["before"] == origin["after"]
assert origin["commit"] == "860b6c503a4261a6c4dd86b803f4cf270ce95c74"
assert not git("status", "--porcelain=v1")
head, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
assert head == "db14f824da52e83ab392a0096c9dd1bbb0895c29"
changed = git("diff", "--name-only", origin["commit"], head).splitlines()
assert changed == ["tests/ir/raise_cold.attrs"]
assert not git("diff", "--summary", origin["commit"], head)
path = changed[0]
old = git_bytes("show", origin["commit"] + ":" + path)
new = git_bytes("show", head + ":" + path)
expected = old
for helper in (b"check", b"enter"):
    before = b"@pys.recursion." + helper + b": alwaysinline\n"
    assert expected.count(before) == 1
    expected = expected.replace(before, b"@pys.recursion." + helper + b":\n")
assert new == expected == (repo / path).read_bytes()

def snapshot():
    names = git_bytes("ls-files", "-z", "--cached", "--others", "--exclude-standard").decode().split("\0")
    paths = {name for name in names if name and (name in ["pystachy.py", "runtime.c", "runtime.py", "pyembed.c", "pyext.c"]
             or name.startswith(("src/", "lib/", "ryu/", "mpz/")))}
    for folder in ("src", "lib", "ryu", "mpz"):
        paths.update(str(p.relative_to(repo)) for p in (repo / folder).rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts)
    return {name: file_digest(repo / name) for name in sorted(paths)
            if (repo / name).is_file() and not name.endswith(".pyc")}

before = snapshot()
assert before == origin["after"]
extra = {}
for path in ("Makefile", "VERSION", ".python-version"):
    contents = git_bytes("show", origin["commit"] + ":" + path)
    assert contents == git_bytes("show", head + ":" + path) == (repo / path).read_bytes()
    extra[path] = {"bytes": len(contents), "sha256": digest(contents)}
assert len(origin["artifacts"]) == 9
for path, info in origin["artifacts"].items():
    artifact = repo / path
    assert artifact.stat().st_size == info["bytes"] and file_digest(artifact) == info["sha256"]
assert len({origin["artifacts"][f"build/stage{n}.ll"]["sha256"] for n in (1, 2, 3)}) == 1
assert len({origin["artifacts"][f"build/rt{n}.ll"]["sha256"] for n in (1, 2, 3)}) == 1
assert file_digest(origin_path.parent / "bootstrap.log") == origin["log_sha256"]
after = snapshot()
assert before == after and not git("status", "--porcelain=v1")
assert git("rev-parse", "HEAD") == head
record = dict(
    schema=1, record_kind="equivalent_build_binding", status="complete",
    scope="Revalidated unchanged compiler/build/runtime inputs after an exact two-line test-oracle correction. No new bootstrap or compiler execution occurred. Final-head fresh CI is separate.",
    source=str(repo), commit=head, tree=tree, before=before, after=after,
    source_identity_stable=True, artifacts=origin["artifacts"],
    fresh_local_build=False, build_command_executed=False,
    exit_code=origin["exit_code"], exit_code_scope="The completed originating bootstrap, not a new command.",
    python=origin["python"], llvm=origin["llvm"],
    build_origin=dict(record_path=str(origin_path), record_sha256=file_digest(origin_path),
                      commit=origin["commit"], tree=origin["tree"], seconds=origin["seconds"],
                      fresh_local_build=True, log_path=str(origin_path.parent / "bootstrap.log"),
                      log_sha256=origin["log_sha256"]),
    equivalence=dict(changed_paths=changed, old_oracle_sha256=digest(old), new_oracle_sha256=digest(new),
                     diff_sha256=digest(git_bytes("diff", "--binary", origin["commit"], head)),
                     compiled_input_count=len(before), extra_build_inputs=extra,
                     verified_artifacts=9, exact_oracle_replacement=True),
    binding_script_sha256=file_digest(__file__),
    recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
assert not destination.exists()
destination.write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({key: record[key] for key in ("status", "commit", "tree", "record_kind", "fresh_local_build")}))
