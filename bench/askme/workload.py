"""Build the steady-state AskMe workload: one long scripted run.

The committed scenarios finish in a few model requests, so they measure
process startup more than the harness. This generator scripts TASKS tasks of
STEPS executor steps each: reads, searches, edits, writes, appends and tree
listings over a small project, with no shell action, so the time measured is
the harness's own work per step. ``build`` scans 240-line files (navigation
dominates); ``build_light`` uses tiny files (controller work dominates).
Every reply is fixed in advance; no model is involved.

usage: workload.py OUTPUT.json [TASKS] [STEPS]
"""

import json
import sys


def text_reply(obj):
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": json.dumps(obj)},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 120, "completion_tokens": 24, "total_tokens": 144},
        "model": "recorded-model",
    }


def tool_reply(name, **arguments):
    call = {"id": "call_0", "type": "function"}
    call["function"] = {"name": name, "arguments": json.dumps(arguments)}
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": None, "tool_calls": [call]},
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 310, "completion_tokens": 42, "total_tokens": 352},
        "model": "recorded-model",
    }


def build(tasks, steps, lines=240, modules=6, handlers=40):
    """TASKS tasks of STEPS scripted steps over files of LINES records."""
    if lines < 2 * (steps // 10 + 1):
        raise ValueError("too few lines for this many edit steps")
    files = {}
    for k in range(tasks):
        files[f"data/batch_{k:02d}.txt"] = "".join(
            f"line {n}: batch {k} record {n} payload {'x' * (n % 37)}\n" for n in range(1, lines + 1)
        )
    for k in range(modules):
        files[f"src/module_{k}.py"] = "".join(
            f"def handler_{k}_{n}(value):\n    return value + {n}\n\n" for n in range(handlers)
        )
    files["README.md"] = "# Records\n\nBatches of numbered records.\n"

    replay = [text_reply({"tasks": [f"Process batch {k:02d}" for k in range(tasks)]})]
    for k in range(tasks):
        target = f"data/batch_{k:02d}.txt"
        for i in range(steps - 1):
            kind = i % 10
            if kind == 0:
                replay.append(tool_reply("read", arg=target, offset=1 + (i * 7) % lines, limit=20))
            elif kind == 1:
                replay.append(tool_reply("search", arg=f"record {1 + i % lines} ", path="data"))
            elif kind == 2:
                n = 1 + i // 10
                replay.append(
                    tool_reply("edit", arg=target, find=f"line {n}:", replace=f"LINE {n} (seen):")
                )
            elif kind == 3:
                module = f"src/module_{i % modules}.py"
                replay.append(tool_reply("read", arg=module, offset=1, limit=60))
            elif kind == 4:
                body = "".join(f"summary {k} {i} {j}\n" for j in range(24))
                replay.append(tool_reply("write", arg=f"out/b{k:02d}_s{i:03d}.txt", content=body))
            elif kind == 5:
                replay.append(tool_reply("tree", arg="src" if i % 20 else "."))
            elif kind == 6:
                replay.append(tool_reply("search", arg=f"handler_{i % modules}_{i % handlers}("))
            elif kind == 7:
                replay.append(
                    tool_reply("write", arg=f"out/log_{k:02d}.txt", content=f"step {i}\n", append=True)
                )
            elif kind == 8:
                replay.append(tool_reply("read", arg=target, offset=1 + (i * 13) % lines))
            else:
                n = lines - i // 10
                replay.append(
                    tool_reply("edit", arg=target, find=f"line {n}:", replace=f"LINE {n} (done):")
                )
        replay.append(tool_reply("done", reasoning="batch processed"))
    return {
        "prompt": "Process every batch of records",
        "args": ["--max-tasks", str(tasks), "--max-steps", str(steps)],
        "env": {"AGENT_FINAL_VALIDATE": "0"},
        "files": files,
        "exit_code": 0,
        "replay": replay,
    }


def build_light(tasks, steps):
    """The same script over tiny files: controller work dominates file scanning."""
    return build(tasks, steps, lines=2 * (steps // 10 + 1) + 2, modules=2, handlers=4)


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    tasks = int(argv[2]) if len(argv) > 2 else 20
    steps = int(argv[3]) if len(argv) > 3 else 100
    with open(argv[1], "w", encoding="utf-8") as stream:
        json.dump(build(tasks, steps), stream)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
