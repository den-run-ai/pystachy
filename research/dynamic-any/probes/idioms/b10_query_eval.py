# pystachy: dynamic-any
# a JMESPath-like query subset evaluated over a document: fields, indexes, projections, filters
from typing import Any


def tokens(expr: str) -> list[str]:
    out: list[str] = []
    cur = ""
    for ch in expr:
        if ch in ".[]*?=":
            if cur:
                out.append(cur)
            cur = ""
            out.append(ch)
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def evaluate(expr: str, doc: Any) -> Any:
    cur: Any = doc
    projecting = False
    toks = tokens(expr)
    i = 0
    while i < len(toks):
        t = toks[i]
        if t == ".":
            i += 1
            continue
        if t == "[":
            if toks[i + 1] == "*":
                projecting = True
                i += 3
                continue
            idx = int(toks[i + 1])
            if projecting:
                cur = [x[idx] for x in cur if isinstance(x, list) and -len(x) <= idx < len(x)]
            else:
                cur = cur[idx] if isinstance(cur, list) and -len(cur) <= idx < len(cur) else None
            i += 3
            continue
        if projecting:
            cur = [x[t] for x in cur if isinstance(x, dict) and t in x]
        else:
            cur = cur.get(t) if isinstance(cur, dict) else None
        i += 1
    return cur


doc = {"reservations": [{"instances": [{"id": "i-1", "state": "running", "cpu": 2}, {"id": "i-2", "state": "stopped", "cpu": 0.5}]},
                        {"instances": [{"id": "i-3", "state": "running", "cpu": 4}]}],
       "owner": {"name": "ops", "tags": ["a", "b"]}}
for q in ["owner.name", "owner.tags[1]", "reservations[0].instances[1].cpu", "reservations[*].instances", "owner.missing"]:
    print(q, "->", evaluate(q, doc))
