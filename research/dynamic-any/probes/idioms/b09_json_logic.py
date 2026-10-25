# pystachy: dynamic-any
# a JSON-Logic-style rule evaluator: rules and data are nested heterogeneous documents
from typing import Any


def var(data: Any, path: Any) -> Any:
    cur = data
    for part in str(path).split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur


def truthy(x: Any) -> bool:
    if isinstance(x, list):
        return len(x) > 0
    return bool(x)


def apply(rule: Any, data: Any) -> Any:
    if not isinstance(rule, dict):
        return rule
    op = list(rule.keys())[0]
    args = rule[op]
    if not isinstance(args, list):
        args = [args]
    if op == "var":
        return var(data, args[0])
    if op == "if":
        i = 0
        while i + 1 < len(args):
            if truthy(apply(args[i], data)):
                return apply(args[i + 1], data)
            i += 2
        return apply(args[i], data) if i < len(args) else None
    vals = [apply(a, data) for a in args]
    if op == "and":
        for v in vals:
            if not truthy(v):
                return v
        return vals[-1]
    if op == "or":
        for v in vals:
            if truthy(v):
                return v
        return vals[-1]
    if op == "==":
        return vals[0] == vals[1]
    if op == ">":
        return vals[0] > vals[1]
    if op == "<":
        return vals[0] < vals[1]
    if op == "+":
        t: Any = 0
        for v in vals:
            t = t + v
        return t
    if op == "in":
        return vals[0] in vals[1]
    if op == "cat":
        return "".join(str(v) for v in vals)
    raise ValueError("unknown op " + op)


rules = [
    {"if": [{">": [{"var": "temp"}, 30]}, "hot", {"<": [{"var": "temp"}, 5]}, "cold", "mild"]},
    {"and": [{"==": [{"var": "user.role"}, "admin"]}, {"in": ["beta", {"var": "user.flags"}]}]},
    {"+": [{"var": "a"}, {"var": "b"}, 0.5]},
    {"cat": ["Hello, ", {"var": "user.name"}, "!"]},
    {"var": "items.1.price"},
]
data = [
    {"temp": 35, "user": {"role": "admin", "flags": ["beta"], "name": "Ann"}, "a": 1, "b": 2, "items": [{"price": 1}, {"price": 2.5}]},
    {"temp": 2.5, "user": {"role": "dev", "flags": [], "name": "Bo"}, "a": 1.5, "b": 2, "items": []},
]
for d in data:
    print([apply(r, d) for r in rules])
