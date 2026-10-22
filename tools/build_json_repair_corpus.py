"""Collect replayable, schema-free API inputs from pinned upstream test sources.

This is an input corpus, not a claim to execute the complete upstream test suite.
Only literal/resolvable call arguments are extracted; exclusions are reported.
"""
import argparse
import ast
import hashlib
import itertools
import json
from pathlib import Path
import sys
import subprocess

ROOT = Path(__file__).resolve().parent
UPSTREAM = ROOT / "upstream"

FILES = ["test_json_repair.py", "test_parse_array.py", "test_parse_comment.py",
         "test_parse_number.py", "test_parse_object.py", "test_parse_string.py",
         "test_strict_mode.py"]
FLAGS = {"skip_json_loads", "stream_stable", "strict", "logging",
         "return_objects", "ensure_ascii"}

def value(node, env):
    if isinstance(node, ast.Name):
        return env[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mult)):
        a, b = value(node.left, env), value(node.right, env)
        return a + b if isinstance(node.op, ast.Add) else a * b
    if isinstance(node, ast.JoinedStr):
        parts = []
        for part in node.values:
            if isinstance(part, ast.FormattedValue):
                if part.conversion != -1 or part.format_spec is not None:
                    raise ValueError("unresolved format specifier")
                parts.append(str(value(part.value, env)))
            else:
                parts.append(value(part, env))
        return "".join(parts)
    return ast.literal_eval(node)


def bind(target, val, env):
    if isinstance(target, ast.Name):
        env[target.id] = val
    elif isinstance(target, (ast.Tuple, ast.List)) and len(target.elts) == len(val):
        for element, item in zip(target.elts, val):
            bind(element, item, env)
    else:
        raise ValueError("unresolved assignment target")


def forget(target, env):
    for node in ast.walk(target):
        if isinstance(node, ast.Name):
            env.pop(node.id, None)


def calls_with_env(node, env, helpers=None):
    """Expand literal loops without executing upstream test source.

    Unknown control flow is traversed as input discovery, not test execution.
    Bindings are copied for each literal loop iteration so values from the last
    iteration cannot silently replace earlier inputs.
    """
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        try:
            bind(node.targets[0], value(node.value, env), env)
        except (ValueError, TypeError, KeyError):
            forget(node.targets[0], env)
    if isinstance(node, ast.If):
        try:
            condition = value(node.test, env)
        except (ValueError, TypeError, KeyError):
            for branch in (node.body, node.orelse):
                nested_env = dict(env)
                for child in branch:
                    yield from calls_with_env(child, nested_env, helpers)
            for child in ast.walk(node):
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                    env.pop(child.id, None)
        else:
            for child in node.body if condition else node.orelse:
                yield from calls_with_env(child, env, helpers)
        return
    if isinstance(node, ast.For):
        try:
            variants = value(node.iter, env)
            if not isinstance(variants, (list, tuple)) or len(variants) > 100:
                raise ValueError("unresolved loop")
        except (ValueError, TypeError, KeyError):
            variants = None
        if variants is not None:
            for variant in variants:
                nested_env = dict(env)
                bind(node.target, variant, nested_env)
                for child in node.body:
                    yield from calls_with_env(child, nested_env, helpers)
            for child in node.orelse:
                yield from calls_with_env(child, dict(env), helpers)
            return
        forget(node.target, env)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in ("repair_json", "loads")):
        yield node, dict(env)
    elif (helpers and isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
          and node.func.id in helpers):
        helper = helpers[node.func.id]
        try:
            if node.keywords or len(node.args) != len(helper.args.args):
                raise ValueError("unresolved helper arguments")
            bindings = {arg.arg: value(actual, env) for arg, actual in zip(helper.args.args, node.args)}
        except (ValueError, TypeError, KeyError):
            bindings = {}
        # Only one helper level: never recursively evaluate arbitrary test code.
        yield from calls_with_env(helper, bindings)
    for child in ast.iter_child_nodes(node):
        yield from calls_with_env(child, env, helpers)


def request(node, env):
    api = node.func.id
    if len(node.args) != 1:
        raise ValueError("unresolved positional arguments")
    raw = value(node.args[0], env)
    if not isinstance(raw, str):
        raise ValueError("non-string input")
    # The replay runner defaults to objects for task cases. Extracted calls
    # retain upstream's actual default serialization and the called API.
    flags = {"return_objects": False} if api == "repair_json" else {}
    for kw in node.keywords:
        if kw.arg not in FLAGS or (api == "loads" and kw.arg in {"return_objects", "ensure_ascii"}):
            raise ValueError("out-of-scope keyword " + str(kw.arg))
        flag = value(kw.value, env)
        if not isinstance(flag, bool):
            raise ValueError("non-bool flag")
        flags[kw.arg] = flag
    if len(raw) > 30000:
        raise ValueError("large stress case")
    return raw, flags, api

def typed(obj):
    """Preserve bool/int distinction, float value, key order and code points."""
    if obj is None:
        return ["none"]
    if isinstance(obj, bool):
        return ["bool", obj]
    if isinstance(obj, int):
        return ["int", str(obj)]
    if isinstance(obj, float):
        return ["float", obj.hex()]
    if isinstance(obj, str):
        # JSON escaping alone is not injective: two surrogate characters and
        # the corresponding astral code point serialize to identical escapes.
        return ["str", [ord(char) for char in obj]]
    if isinstance(obj, list):
        return ["list", [typed(v) for v in obj]]
    if isinstance(obj, tuple):
        return ["tuple", [typed(v) for v in obj]]
    if isinstance(obj, dict):
        return ["dict", [[typed(k), typed(v)] for k, v in obj.items()]]
    raise TypeError(type(obj))

def outcome(raw, flags, api="repair_json"):
    try:
        kwargs = dict(flags)
        if api == "loads":
            return {"value": typed(loads(raw, **kwargs))}
        kwargs.setdefault("return_objects", True)
        return {"value": typed(repair_json(raw, **kwargs))}
    except Exception as exc:
        return {"error": type(exc).__name__, "message": str(exc)}

def main():
    global UPSTREAM, loads, repair_json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, default=UPSTREAM)
    parser.add_argument("--output", type=Path, default=ROOT)
    args = parser.parse_args()
    UPSTREAM = args.upstream.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"], text=True).strip()
    if commit != "ace9b23cb7fc6757775d5fafbfaaa9a88363a573":
        raise SystemExit("Expected json_repair v0.64.1 commit ace9b23cb7fc6757775d5fafbfaaa9a88363a573")
    if subprocess.check_output(["git", "-C", str(UPSTREAM), "status", "--porcelain", "--untracked-files=no"], text=True):
        raise SystemExit("Upstream source checkout has tracked modifications")
    sys.path.insert(0, str(UPSTREAM / "src"))
    from json_repair import loads, repair_json
    rows, seen, excluded = [], {}, []

    def add(raw, flags, source, api="repair_json"):
        key = (api, raw, tuple(sorted(flags.items())))
        if key in seen:
            rows[seen[key]]["sources"].append(source)
            return
        seen[key] = len(rows)
        rows.append({"id": len(rows), "api": api, "input": raw, "flags": flags,
                     "sources": [source], "expected": outcome(raw, flags, api)})

    for filename in FILES:
        path = UPSTREAM / "tests" / filename
        tree = ast.parse(path.read_text())
        helpers = {func.name: func for func in tree.body if isinstance(func, ast.FunctionDef)
                   and func.name == "_assert_object_repairs"}
        for func in tree.body:
            if not isinstance(func, ast.FunctionDef):
                continue
            if func.name in helpers:
                continue
            envs = [{}]
            for decorator in func.decorator_list:
                if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr == "parametrize"):
                    continue
                try:
                    names = ast.literal_eval(decorator.args[0])
                    names = [n.strip() for n in names.split(",")] if isinstance(names, str) else list(names)
                    vals = ast.literal_eval(decorator.args[1])
                    variants = [dict(zip(names, (v,) if len(names) == 1 else v)) for v in vals]
                    envs = [{**env, **var} for env, var in itertools.product(envs, variants)]
                except (ValueError, TypeError, IndexError):
                    pass
            for env in envs:
                for node, call_env in calls_with_env(func, env, helpers):
                    source = f"tests/{filename}:{node.lineno} ({func.name})"
                    try:
                        raw, flags, api = request(node, call_env)
                        add(raw, flags, source, api)
                    except (ValueError, TypeError, KeyError, IndexError) as exc:
                        excluded.append({"source": source, "reason": str(exc)})

    user_cases = {'valid': '{"tool":"search","args":{"query":"redwoods","k":3},"ok":false}', 'trailing_comma': '{"a":1,"b":[2,3,],}', 'missing_comma': '{"a":1 "b":2}', 'unquoted_keys': '{tool: "search", args: {query: "redwoods"}}', 'python_dict': "{'ok': True, 'value': None}", 'comment': '{"a":1, // note\n "b":2}', 'fenced': chr(96) * 3 + 'json\n{"a":1}\n' + chr(96) * 3, 'prose': 'Here is the result:\n{"a":1}\nHope this helps.', 'raw_newline': '{"text":"line1\nline2"}', 'truncated_containers': '{"a":[1,2', 'missing_value': '{"pass":}', 'cut_false': '{"pass":fal', 'cut_number': '{"budget":15', 'curly_quotes': '{“a”: “one, two”, “b”: true}', 'inner_quotes': '{"text":"He said "hello" to me","ok":true}', 'partial_key': '{"text', 'two_objects': '{"step":1}\n{"step":2}', 'duplicate_keys': '{"tool":"read","tool":"delete"}', 'positive_exponent': '{"value":1e+10', 'numeric_identifier': '{"sku":123_456ABC}', 'surrogate_pair': '{"v":"\\ud83d\\ude00",}', 'double_encoded_args': '{"name":"search","arguments":"{\\"query\\":\\"redwoods\\",}"}'}
    user_cases.update({
        "nested_mixed": '{"events":[{"ok":true,"n":1,"x":1.5,"nil":null,"items":[false,"s",{},[]]},],}',
        "code_exact": '{"code":"def f(x):\\n    return x + 1\\n","path":"C:\\\\tmp\\\\a.py",}',
        "unicode_literals": '{"text":"Привет 中文 😀 café",}',
        "negative_zero": '{"x":-0.0,"y":0.0,}',
        "max_int": '{"max":9223372036854775807,"min":-9223372036854775808}',
        "float_exponents": '{"n":1E-3,"p":-2.5e+2,}',
        "same_shapes": '[1,true,1.0,null,"1",[1],{"a":1},]',
    })
    for name, raw in user_cases.items():
        for flags in ({}, {"strict": True}, {"stream_stable": True}, {"skip_json_loads": True}):
            add(raw, flags, "task:" + name)

    for name, raw in user_cases.items():
        for flags in ({"return_objects": False},
                      {"return_objects": False, "ensure_ascii": False},
                      {"logging": True, "return_objects": False}):
            add(raw, flags, "task-api:" + name)
    for name in ("valid", "unquoted_keys", "surrogate_pair", "nested_mixed"):
        add(user_cases[name], {}, "task-loads:" + name, api="loads")

    manifest = {"upstream": "mangiucugna/json_repair", "tag": "v0.64.1",
                "commit": "ace9b23cb7fc6757775d5fafbfaaa9a88363a573",
                "python": sys.version, "count": len(rows), "excluded_call_variants": excluded,
                "test_sha256": {name: hashlib.sha256((UPSTREAM / "tests" / name).read_bytes()).hexdigest() for name in FILES},
                "source_sha256": {str(p.relative_to(UPSTREAM)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((UPSTREAM / "src" / "json_repair").rglob("*.py"))}}
    (output / "cases.json").write_text("[\n" + ",\n".join(json.dumps(row, ensure_ascii=True, separators=(",", ":")) for row in rows) + "\n]\n")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"{len(rows)} cases, {len(excluded)} excluded call variants")

if __name__ == "__main__":
    main()
