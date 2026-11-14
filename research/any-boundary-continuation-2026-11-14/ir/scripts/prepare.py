"""Pin source homes and native build identities before a complete IR audit."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parent
REPO = WORK / "pystachy"
BASE = WORK / "pystachy"
BASE_REF = "adac7f4c88fd86ddaecbb889042b778c701b29ed"


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text, before, after):
    assert text.count(before) == 1, before
    return text.replace(before, after)


def cases(home):
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}
    canonical = subprocess.check_output(["sh", "-c", ". tests/corpus.sh\ncorpus\n"],
                                        cwd=home, env=env, text=True).splitlines()
    listing = '''for f in pystachy.py runtime.py tests/programs/*/*.py tests/deviations/*.py bench/*.py bench/pyperformance/*.py tests/ir/*.py tests/errors/*/*.py; do
  [ ! -f "$f" ] || printf '%s\\n' "$f"
done
'''
    full = subprocess.check_output(["sh", "-c", listing], cwd=home, env=env, text=True).splitlines()
    assert len(full) == len(set(full))
    assert set(canonical) <= set(full)
    return canonical, full


def snapshot(key, repo, ref, binary, evidence):
    assert not git(repo, "status", "--porcelain", "--untracked-files=all").strip()
    home = ROOT / ("home-" + key)
    home.mkdir()
    archive = git(repo, "archive", ref)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        source.extractall(home, filter="data")
    for name in ("commit", "REVISION"):
        (home / name).write_text(ref + "\n")
    files = {str(p.relative_to(home)): sha(p) for p in sorted(home.rglob("*")) if p.is_file()}
    prefixes = [str(ROOT / ("home-" + name)).encode() for name in ("old", "new")]
    for name in files:
        data = (home / name).read_bytes()
        assert not any(prefix in data for prefix in prefixes), name
    shutil.copy2(binary, home / "pystachy")
    canonical, full = cases(home)
    assert set(full) <= set(files)
    result = {"key": key, "home": str(home), "source_ref": ref,
              "source_tree": git(repo, "rev-parse", ref + "^{tree}").decode().strip(),
              "archive_sha256": hashlib.sha256(archive).hexdigest(),
              "source_files": files, "binary_source": str(binary), "binary_sha256": sha(home / "pystachy"),
              "evidence": evidence, "canonical_count": len(canonical),
              "cases": [{"path": p, "source_sha256": files[p]} for p in full]}
    (ROOT / (key + "-identity.json")).write_text(json.dumps(result, indent=2) + "\n")
    (ROOT / (key + "-cases.txt")).write_text("\n".join(full) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--bootstrap-log", required=True, type=Path)
    parser.add_argument("--bootstrap-manifest", required=True, type=Path)
    args = parser.parse_args()
    assert len(str(ROOT / "home-old")) == len(str(ROOT / "home-new"))
    baseline_manifest = Path("/workspace/scratch/6e931c3f8732/integrated-effects-bootstrap-manifest.json")
    baseline = json.loads(baseline_manifest.read_text())
    baseline_binary = Path("/workspace/scratch/6e931c3f8732/pystachy/pystachy")
    assert sha(baseline_binary) == baseline["binary"]
    inputs = ["pystachy.py", "pystachy_cli.py", "pystachy_toolchain.py", "src", "lib",
              "runtime.c", "runtime.py", "ryu", "mpz", "lljit.c", "VERSION", ".python-version"]
    assert not git(REPO, "diff", "--name-only", baseline["source_commit"], BASE_REF, "--", *inputs).strip()
    candidate_build = json.loads(args.bootstrap_manifest.read_text())
    assert git(REPO, "rev-parse", "HEAD").decode().strip() == args.candidate
    assert not git(REPO, "diff", "--name-only", candidate_build["commit"], args.candidate,
                   "--", *inputs).strip()
    assert sha(REPO / "pystachy") == candidate_build["binary_sha256"]
    assert sha(args.bootstrap_log) == candidate_build["log_sha256"]
    assert candidate_build["exit_code"] == 0 and candidate_build["native_inputs_unchanged"]
    for name, expected in candidate_build["native_input_hashes"].items():
        assert sha(REPO / name) == expected, name
    old = snapshot("old", BASE, BASE_REF, baseline_binary,
                   {"manifest": str(baseline_manifest), "manifest_sha256": sha(baseline_manifest),
                    "build_source": baseline["source_commit"], "identical_native_inputs": inputs})
    text = args.bootstrap_log.read_text()
    assert "fixed point: stage1 == stage2 == stage3 (" in text
    assert "fixed point: runtime.py's IR, rt1 == rt2 == rt3 (" in text
    groups = (("stage1.ll", "stage2.ll", "stage3.ll"), ("rt1.ll", "rt2.ll", "rt3.ll"))
    for group in groups:
        assert len({sha(REPO / "build" / n) for n in group}) == 1, group
        for name in group:
            assert sha(REPO / "build" / name) == candidate_build["fixedpoints"][name]
    assert sha(REPO / "pystachy") == sha(REPO / "build/pystachy2")
    new = snapshot("new", REPO, args.candidate, REPO / "pystachy",
                   {"candidate_ref": args.candidate,
                    "manifest": str(args.bootstrap_manifest), "manifest_sha256": sha(args.bootstrap_manifest),
                    "build_source": candidate_build["commit"], "identical_native_inputs": inputs,
                    "bootstrap_log": str(args.bootstrap_log), "bootstrap_log_sha256": sha(args.bootstrap_log),
                    "fixedpoint_hashes": {n: sha(REPO / "build" / n) for group in groups for n in group}})
    for name, expected in candidate_build["native_input_hashes"].items():
        assert new["source_files"][name] == expected, name
    old_cases = {x["path"]: x["source_sha256"] for x in old["cases"]}
    new_cases = {x["path"]: x["source_sha256"] for x in new["cases"]}
    inventory = {"baseline_count": len(old_cases), "candidate_count": len(new_cases),
                 "added_paths": sorted(new_cases.keys() - old_cases.keys()),
                 "removed_paths": sorted(old_cases.keys() - new_cases.keys()),
                 "changed_sources": sorted(p for p in old_cases.keys() & new_cases.keys() if old_cases[p] != new_cases[p])}
    (ROOT / "inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    audit_cases = [{"argument": p, "kind": "candidate", "path": p,
                    "source_ref": new["source_ref"], "source_sha256": new_cases[p]}
                   for p in new_cases]
    for p in sorted(set(inventory["removed_paths"]) | set(inventory["changed_sources"])):
        audit_cases.append({"argument": str(Path(old["home"]) / p),
                            "kind": "original-baseline-source", "path": p,
                            "source_ref": old["source_ref"], "source_sha256": old_cases[p]})
    (ROOT / "audit-cases.json").write_text(json.dumps(audit_cases, indent=2) + "\n")
    original = (Path(new["home"]) / "tools/irsame.sh").read_text()
    script = replace_once(original, 'cd "$(dirname "$0")/.." || exit 1', 'cd ' + new["home"] + ' || exit 1')
    script = replace_once(script, "SHOW=3", "SHOW=99999")
    script = replace_once(script, "trap 'rm -rf \"$T\"' EXIT", 'echo "Audit directory: $T"\ntrap \'echo "Audit retained: $T"\' EXIT')
    script = replace_once(script, "same() {\n", 'same() {\n  printf \'%s\\n\' "$1" > "$2/case"\n  sha256sum "$1" > "$2/source.sha256"\n')
    script = replace_once(script, '    how=ir\n', '    printf \'%s\\n\' "$mp" > "$2/search-path"\n    how=ir\n')
    script = replace_once(script, '    PYSTACHY_PATH=$mp $OLD $how', '    printf \'%s\\n\' "$how" > "$2/mode"\n    PYSTACHY_PATH=$mp $OLD $how')
    script = replace_once(script, "  messages=0\n", '''  printf '%s\\n' "$a" > "$2/old.status"
  printf '%s\\n' "$b" > "$2/new.status"
  for side in old new; do
    sha256sum "$2/$side.msg" > "$2/$side.msg.sha256"
    if [ -f "$2/$side.ll" ]; then
      sha256sum "$2/$side.ll" > "$2/$side.ir.sha256"
      wc -c < "$2/$side.ll" > "$2/$side.ir.bytes"
    else
      printf '%s\\n' missing > "$2/$side.ir.sha256"
      printf '%s\\n' 0 > "$2/$side.ir.bytes"
    fi
  done
  messages=0
''')
    script = replace_once(script, '  rm -f "$2/old.ll" "$2/new.ll"\n', '''  if [ -s "$2/report" ]; then
    diff -u "$2/old.msg" "$2/new.msg" > "$2/messages.raw.diff" || :
    if [ -f "$2/old.ll" ] && [ -f "$2/new.ll" ]; then
      diff -u "$2/old.ll" "$2/new.ll" > "$2/ir.raw.diff" || :
    fi
  else
    rm -f "$2/old.ll" "$2/new.ll"
  fi
''')
    path = ROOT / "retaining-irsame.sh"
    path.write_text(script)
    subprocess.run(["sh", "-n", str(path)], check=True)
    (ROOT / "oracle.json").write_text(json.dumps({"original_sha256": sha(Path(new["home"]) / "tools/irsame.sh"),
        "wrapper": str(path), "wrapper_sha256": sha(path),
        "audit_cases_sha256": sha(ROOT / "audit-cases.json"),
        "semantics": "Unchanged tools/irsame.sh comparison, retaining all changed IR/messages and status/hash evidence for every final corpus input plus exact removed/changed original baseline case bytes"}, indent=2) + "\n")
    print(json.dumps({"old": old["source_ref"], "new": new["source_ref"], "inventory": inventory}, indent=2))


if __name__ == "__main__":
    main()
