"""Writes a deterministic JSONL transcript of coding-agent events with mixed field types."""
import json
import random
import sys

r = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
n = int(sys.argv[1])
tools = ["Bash", "Read", "Edit", "Grep", "WebFetch"]
cmds = ["make test", "git status", "ls -la", "python3 x.py", "rg foo", "cat a.txt"]
pending = []
out = []
for i in range(n):
    s = "s%d" % r.randrange(8)
    k = r.random()
    if k < 0.35 or not pending:
        tid = "t%d" % i
        name = r.choice(tools)
        if name == "Bash":
            inp = {"command": r.choice(cmds)}
            if r.random() < 0.6:
                inp["timeout"] = r.choice([120, 600, 30.5])
            if r.random() < 0.2:
                inp["run_in_background"] = True
        elif name == "Read":
            inp = {"file_path": "/src/%s.%s" % (r.choice("abcde"), r.choice(["py", "md", "c"])), "limit": r.choice([None, 50, 200])}
        elif name == "Edit":
            inp = {"file_path": "/src/m%d.py" % r.randrange(5), "old": "x" * r.randrange(1, 40), "new": "y" * r.randrange(0, 60), "replace_all": r.random() < 0.1}
        elif name == "Grep":
            inp = {"pattern": r.choice(["foo", "def \\w+", "TODO", "[0-9]+"]), "glob": r.choice(["*.py", None, ["*.c", "*.h"]])}
        else:
            inp = {"url": "https://example.org/%d" % r.randrange(100), "max_bytes": r.choice([1000, "unlimited", 2.5e4])}
        out.append({"ts": i, "session": s, "type": "tool_use", "id": tid, "name": name, "input": inp})
        pending.append(tid)
    elif k < 0.70:
        tid = pending.pop(r.randrange(len(pending)))
        content = r.choice(["ok", "done\nmore", [{"type": "text", "text": "line " * r.randrange(1, 6)}], [{"type": "text", "text": "a"}, {"type": "image", "bytes": r.randrange(9999)}]])
        dur = r.choice([r.randrange(1, 5000), r.random() * 900, None])
        out.append({"ts": i, "session": s, "type": "tool_result", "tool_use_id": tid, "is_error": r.random() < 0.12, "content": content, "duration_ms": dur})
    elif k < 0.85:
        cache = r.choice([None, r.randrange(0, 50000)])
        cost = r.choice([round(r.random() / 10, 6), "n/a", 0])
        out.append({"ts": i, "session": s, "type": "usage", "input_tokens": r.randrange(10, 20000), "output_tokens": r.randrange(1, 4000), "cache_read_input_tokens": cache, "cost": cost})
    elif k < 0.97:
        out.append({"ts": i, "session": s, "type": "text", "text": "word " * r.randrange(1, 30)})
    else:
        out.append({"ts": i, "session": s, "type": "error", "message": "boom %d" % i, "code": r.choice([500, 429, "overloaded", None])})
sys.stdout.write("\n".join(json.dumps(e) for e in out) + "\n")
