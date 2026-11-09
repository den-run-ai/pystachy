"""usage: python3 -I check_issue.py WORKTREE ISSUE_FILE... (first line '# <title>', blank line, body)"""
import importlib.util, pathlib, re, sys
spec = importlib.util.spec_from_file_location("cs", pathlib.Path(sys.argv[1]) / "tools/check_submission.py")
cs = importlib.util.module_from_spec(spec); spec.loader.exec_module(cs)
bad = 0
for p in sys.argv[2:]:
    title, _, body = pathlib.Path(p).read_text().partition("\n")
    title, body = title.removeprefix("# ").strip(), body.strip()
    errs = cs.validate(title, body)
    words = len(re.sub(r"<!--.*?-->", "", body, flags=re.S).split())
    print(pathlib.Path(p).name, errs or "OK", f"title={len(title)}", f"words={words}", f"chars={len(body)}")
    bad += bool(errs)
sys.exit(1 if bad else 0)
