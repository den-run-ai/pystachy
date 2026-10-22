# pystachy: dynamic-any
"""Small text kernels, not end-to-end router or json_repair benchmarks.

The original repair scanner tolerates single quotes and missing closing quotes;
it only tokenizes/decodes strings, without json_repair's structural heuristics.
"""
import fnmatch
import json
import re
import sys
import time
from typing import Any


def match_batch(n: int) -> int:
    names = ["api.read", "api.write", "db.query", "db.commit", "worker.17", "worker.xx", "other", "API.read"]
    patterns = ["api.*", "db.q?ery", "worker.[0-9][0-9]", "[!a]*.read"]
    total = 0
    for i in range(n):
        for name in names:
            for pattern in patterns:
                total += int(fnmatch.fnmatchcase(name, pattern))
        # Unique patterns force translation and compilation, beyond cache hits.
        prefix = "batch" + str(i)
        match = re.compile(fnmatch.translate(prefix + ".[0-9]?")).match(prefix + ".7x")
        total += int(match is not None)
    return total


def json_score(value: Any) -> int:
    if value is None:
        return 11
    if isinstance(value, bool):
        return 7 if value else 3
    if isinstance(value, int):
        return value * 4
    if isinstance(value, float):
        return int(value * 4.0)
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    total: int = 0
    if isinstance(value, list):
        for item in value:
            total += json_score(item)
    elif isinstance(value, dict):
        for key in value:
            total += len(key) + json_score(value[key])
    return total


def parse_batch(n: int) -> int:
    texts = ['{"id":17,"ok":true,"data":[1,-2,3.5,null,"a\\nb","\\u00e9"]}',
             '[{"k":"quote\\\"slash\\\\","v":false},{"k":"plain","v":{"n":2}}]',
             '[0,1,2,3,4,5,6,7,8,9]']
    total = 0
    for i in range(n):
        for text in texts:
            total += json_score(json.loads(text))
    return total


def repair_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    while i < len(text):
        c = text[i]
        if c in " \t\r\n,:{}[]":
            i += 1
        elif c in "\"'":
            quote = c
            i += 1
            parts: list[str] = []
            start = i
            while i < len(text):
                c = text[i]
                if c == quote or c == "\\":
                    parts.append(text[start:i])
                    i += 1
                    if c == quote:
                        break
                    if i < len(text):
                        escaped = text[i]
                        parts.append("\n" if escaped == "n" else "\t" if escaped == "t" else escaped)
                        i += 1
                    start = i
                else:
                    i += 1
            else:
                parts.append(text[start:i])
            tokens.append("".join(parts))
        else:
            start = i
            while i < len(text) and text[i] not in " \t\r\n,:{}[]\"'":
                i += 1
            tokens.append(text[start:i])
    return tokens


def scan_batch(n: int) -> int:
    texts = ['{name: "short", ok: true,}', "{'name': 'unfinished", '"' + "a\\n" * 2048 + '"']
    total = 0
    for i in range(n):
        for text in texts:
            for token in repair_tokens(text):
                total += len(token) + 1
    return total


def main() -> None:
    mode, n = sys.argv[1], int(sys.argv[2])
    assert n > 0
    # Independent small oracles, outside the timed region.
    assert match_batch(1) == 6
    assert json_score(json.loads('[1,2.5,true,false,null,"x",{"k":[2]}]')) == 45
    assert json.loads(r'"a\nb"') == "a\nb"
    assert json.loads(r'"\u00e9"') == "é"
    assert json.loads(r'"quote\"slash\\"') == 'quote"slash\\'
    assert repair_tokens('{key:"a\\nb", tail: \'unfinished') == ["key", "a\nb", "tail", "unfinished"]
    assert repair_tokens('"\\\"\\\\"') == ['"\\']
    assert repair_tokens('"' + "a\\n" * 2048 + '"') == ["a\n" * 2048]
    start = time.perf_counter()
    if mode == "fnmatch":
        result = match_batch(n)
    elif mode == "json":
        result = parse_batch(n)
    elif mode == "repair_scan":
        result = scan_batch(n)
    else:
        raise ValueError("unknown text kernel")
    elapsed = time.perf_counter() - start
    print(result)
    print("seconds", elapsed, file=sys.stderr)


if __name__ == "__main__":
    main()
