"""Attest final tools-only changes without misidentifying the built compiler source."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent / "pystachy"


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final", required=True)
    parser.add_argument("--published", required=True)
    args = parser.parse_args()
    identity = json.loads((ROOT / "new-identity.json").read_text())
    assert git("rev-parse", "HEAD").decode().strip() == args.final
    assert not git("status", "--porcelain", "--untracked-files=all").strip()
    tree = git("rev-parse", args.final + "^{tree}").decode().strip()
    assert tree == git("rev-parse", args.published + "^{tree}").decode().strip()
    changes = git("diff", "--name-only", identity["source_ref"], args.final).decode().splitlines()
    expected = ["tools/check_lean_storage.py", "tools/lean_boundary/STORAGE.md", "tools/test_lean_storage_generators.py"]
    assert changes == expected, changes
    assert hashlib.sha256((REPO / "pystachy").read_bytes()).hexdigest() == identity["binary_sha256"]
    files = {}
    folder = ROOT / "final-tools"
    folder.mkdir()
    for path in changes:
        data = git("show", args.final + ":" + path)
        assert data == (REPO / path).read_bytes()
        target = folder / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files[path] = {"audited_source_sha256": identity["source_files"].get(path),
                       "final_sha256": hashlib.sha256(data).hexdigest()}
    patch = git("diff", identity["source_ref"], args.final)
    (ROOT / "final-tools.patch").write_bytes(patch)
    result = {"built_and_full_audit_source": identity["source_ref"],
              "built_and_full_audit_published": identity["evidence"]["published_ref"],
              "built_and_full_audit_tree": identity["source_tree"],
              "final_source": args.final, "final_published": args.published, "final_tree": tree,
              "final_published_tree_identical": True, "only_changed_paths": changes, "files": files,
              "compiler_binary_sha256": identity["binary_sha256"],
              "all_compiler_runtime_library_corpus_and_other_tracked_inputs_unchanged": True,
              "patch_sha256": hashlib.sha256(patch).hexdigest(),
              "explanation": "Only the strict-storage adapter, its independent generator controls and its scope documentation changed after the native fixed-point build. The exact built compiler and every full IR audit input remain unchanged. Final Lean qualification uses the corrected adapter; no claim is made that the native binary was rebuilt after a tools-only edit."}
    (ROOT / "final-tree.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
