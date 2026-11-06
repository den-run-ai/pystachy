# pystachy: dynamic-any
"""Agent-transcript analytics: mixed JSONL events -> handlers chosen by type -> per-session state
objects -> aggregation -> a JSON summary. Times decoding and processing separately.

usage: pipeline.py EVENTS.jsonl [ROUNDS]
"""
from __future__ import annotations

import json
import sys
import time
from typing import Any, Callable


def to_any(v: json.JSONValue) -> Any:
    # json.loads() gives JSONValue storage, which cannot become Any (docs/dynamic-any.md): copy it
    if isinstance(v, dict):
        d: dict[Any, Any] = {}
        for k, x in v.items():
            d[k] = to_any(x)
        return d
    if isinstance(v, list):
        out: list[Any] = []
        for x in v:
            out.append(to_any(x))
        return out
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return v
    if isinstance(v, str):
        return v
    return None


def to_json(x: Any) -> json.JSONValue:
    if isinstance(x, dict):
        d: dict[str, json.JSONValue] = {}
        for k in x:
            d[str(k)] = to_json(x[k])
        return d
    if isinstance(x, list) or isinstance(x, tuple):
        out: list[json.JSONValue] = []
        for e in x:
            out.append(to_json(e))
        return out
    if isinstance(x, bool):
        return bool(x)
    if isinstance(x, int):
        return int(x)
    if isinstance(x, float):
        return float(x)
    if isinstance(x, str):
        return str(x)
    return None


class ToolStats:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls = 0
        self.errors = 0
        self.total_ms: Any = 0
        self.timed = 0
        self.keys: dict[Any, Any] = {}

    def summary(self) -> Any:
        mean: Any = None
        if self.timed:
            m = self.total_ms / self.timed
            if isinstance(m, float):  # W2: round() of an Any value is not supported
                mean = round(m, 3)
        top = sorted(self.keys.items(), key=lambda kv: (-kv[1], str(kv[0])))[:3]
        return {"calls": self.calls, "errors": self.errors, "mean_ms": mean, "top": [[str(k), n] for k, n in top]}


class Session:
    def __init__(self, sid: str) -> None:
        self.sid = sid
        self.pending: dict[Any, Any] = {}
        self.tokens_in = 0
        self.tokens_out = 0
        self.cached = 0
        self.cost: Any = 0
        self.unpriced = 0
        self.words = 0
        self.errors: list[Any] = []

    def summary(self) -> Any:
        cost = self.cost
        if isinstance(cost, float):  # W2: round() of an Any value is not supported
            cost = round(cost, 6)
        return {"in": self.tokens_in, "out": self.tokens_out, "cached": self.cached,
                "cost": cost, "unpriced": self.unpriced, "words": self.words,
                "errors": self.errors[:3], "open": len(self.pending)}


class State:
    def __init__(self) -> None:
        self.sessions: dict[Any, Any] = {}
        self.tools: dict[Any, Any] = {}
        self.unknown = 0

    def session(self, sid: Any) -> Any:
        s = self.sessions.get(sid)
        if s is None:
            s = Session(str(sid))
            self.sessions[sid] = s
        return s

    def tool(self, name: Any) -> Any:
        t = self.tools.get(name)
        if t is None:
            t = ToolStats(str(name))
            self.tools[name] = t
        return t


# the key each tool's input contributes to its statistics: a str, an int or a tuple
def key_bash(inp: Any) -> Any:
    cmd = inp["command"]
    first = cmd.split()[0] if cmd else ""
    if inp.get("run_in_background"):
        return first + "&"
    return first


def key_read(inp: Any) -> Any:
    path = inp["file_path"]
    if not isinstance(path, str):  # W1: an Any value cannot be sliced
        return ""
    return path[path.rfind(".") + 1:] if "." in path else ""


def key_edit(inp: Any) -> Any:
    return len(inp["new"]) - len(inp["old"]) > 0


def key_grep(inp: Any) -> Any:
    g = inp.get("glob")
    if isinstance(g, list):
        return len(g)
    return g if g is not None else "-"


def key_fetch(inp: Any) -> Any:
    m = inp.get("max_bytes")
    if isinstance(m, str):
        return m
    return int(m) // 1000


KEYS: dict[str, Callable[[Any], Any]] = {"Bash": key_bash, "Read": key_read, "Edit": key_edit,
                                         "Grep": key_grep, "WebFetch": key_fetch}


def on_tool_use(e: Any, st: Any) -> None:
    s = st.session(e["session"])
    s.pending[e["id"]] = e
    t = st.tool(e["name"])
    t.calls += 1
    keyf = KEYS.get(e["name"])
    if keyf is not None:
        k = keyf(e["input"])
        t.keys[k] = t.keys.get(k, 0) + 1


def on_tool_result(e: Any, st: Any) -> None:
    owner: Any = None
    for s in st.sessions.values():
        if e["tool_use_id"] in s.pending:
            owner = s
            break
    if owner is None:
        st.unknown += 1
        return
    use = owner.pending.pop(e["tool_use_id"])
    t = st.tool(use["name"])
    if e["is_error"]:
        t.errors += 1
    d = e["duration_ms"]
    if d is not None:
        t.total_ms += d
        t.timed += 1
    c = e["content"]
    if isinstance(c, list):
        for block in c:
            if block["type"] == "text":
                owner.words += len(block["text"].split())
    else:
        owner.words += len(c.split())


def on_usage(e: Any, st: Any) -> None:
    s = st.session(e["session"])
    s.tokens_in += e["input_tokens"]
    s.tokens_out += e["output_tokens"]
    c = e["cache_read_input_tokens"]
    if c is not None:
        s.cached += c
    cost = e["cost"]
    if isinstance(cost, str):
        s.unpriced += 1
    else:
        s.cost += cost


def on_text(e: Any, st: Any) -> None:
    st.session(e["session"]).words += len(e["text"].split())


def on_error(e: Any, st: Any) -> None:
    st.session(e["session"]).errors.append([e["code"], e["message"]])


HANDLERS: dict[str, Callable[[Any, Any], None]] = {"tool_use": on_tool_use, "tool_result": on_tool_result,
                                                   "usage": on_usage, "text": on_text, "error": on_error}


def process(events: list[Any]) -> Any:
    st = State()
    for e in events:
        h = HANDLERS.get(e["type"])
        if h is None:
            st.unknown += 1
        else:
            h(e, st)
    sessions: dict[Any, Any] = {}
    for sid in sorted(st.sessions):
        sessions[sid] = st.sessions[sid].summary()
    tools: dict[Any, Any] = {}
    for name in sorted(st.tools):
        tools[name] = st.tools[name].summary()
    return {"events": len(events), "unknown": st.unknown, "sessions": sessions, "tools": tools}


def main() -> None:
    with open(sys.argv[1]) as f:
        lines = f.read().splitlines()
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    dec: list[int] = []
    proc: list[int] = []
    summary: Any = None
    for _ in range(rounds):
        t0 = time.perf_counter_ns()
        events: list[Any] = []
        for ln in lines:
            events.append(to_any(json.loads(ln)))
        t1 = time.perf_counter_ns()
        summary = process(events)
        t2 = time.perf_counter_ns()
        dec.append(t1 - t0)
        proc.append(t2 - t1)
    print(json.dumps(to_json(summary), sort_keys=True))
    if rounds > 1:
        dec.sort()
        proc.sort()
        print(f"decode {dec[len(dec) // 2] / 1e6:.1f} ms median process {proc[len(proc) // 2] / 1e6:.1f} ms")


main()
