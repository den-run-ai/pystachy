"""The complete typed AskMe harness: scripted runs through planner, executor and policies."""
import json
import os
import re
import tempfile

from askme_native import ReplayTransport, run_result
from native_host import read_text, remove_tree, sha256_hex, sha256_pure, write_text
from native_json import JSONValue
from native_llm import LLMSettings, get_capability_profile
from native_loop import RunConfig

SECONDS = re.compile(r"\b\d+\.\d+s\b")
MACHINE_LINES = ("Environment:", "Available tools:", "Missing tools:", "Package managers:")
QUIET_EVENTS = ("run_start", "tokens", "reasoning_decision")

FAKE_CC = """if grep -q '#include <stdio.h>' "$1"; then
  echo "built $1"
  exit 0
fi
echo "$1:3:5: error: implicit declaration of function 'printf'"
exit 1
"""


def text(body: str) -> str:
    return ('{"choices":[{"message":{"content":' + json.dumps(body)
            + '},"finish_reason":"stop"}],"usage":{"prompt_tokens":120,"completion_tokens":24,'
            '"total_tokens":144},"model":"recorded-model"}')


def tool(name: str, arguments: str) -> str:
    return ('{"choices":[{"message":{"content":null,"tool_calls":[{"type":"function","function":'
            '{"name":' + json.dumps(name) + ',"arguments":' + json.dumps(arguments)
            + '}}]},"finish_reason":"tool_calls"}]}')


def scrub(value: JSONValue, workspace: str) -> JSONValue:
    """Drop wall times and the machine's tool inventory; name the workspace <WS>."""
    if isinstance(value, dict):
        cleaned: dict[str, JSONValue] = {}
        for key, item in value.items():
            if key == "environment":
                continue
            if key in ("wall_s", "llm_wall_s"):
                cleaned[key] = 0
            else:
                cleaned[key] = scrub(item, workspace)
        return cleaned
    if isinstance(value, list):
        items: list[JSONValue] = []
        for item in value:
            items.append(scrub(item, workspace))
        return items
    if isinstance(value, str):
        return value.replace(workspace, "<WS>")
    return value


def play(title: str, prompt: str, files: dict[str, str], replies: list[str],
         step_policy: str = "heuristic", final_validate: str = "auto") -> None:
    print("==", title)
    base = tempfile.mkdtemp()
    workspace = os.path.realpath(base) + "/ws"
    os.makedirs(workspace)
    for name, content in files.items():
        os.makedirs(os.path.dirname(workspace + "/" + name), exist_ok=True)
        write_text(workspace + "/" + name, content)
    document = json.loads("[" + ",".join(replies) + "]")
    entries: list[JSONValue] = []
    if isinstance(document, list):
        entries = document
    llm = LLMSettings("local", "http://127.0.0.1:9/v1/chat/completions", "recorded-model", "",
                      "Parasail", True, False, "", 120,
                      get_capability_profile("generic-feature-scale-v1"))
    config = RunConfig(llm, False, True, "gated", 2, 10, 10, 300, final_validate, True, step_policy)
    console: list[str] = []

    def keep(line: str) -> None:
        for prefix in MACHINE_LINES:
            if line.startswith(prefix):
                return
        console.append(SECONDS.sub("0.0s", line.replace(workspace, "<WS>")))

    try:
        result = run_result(prompt, workspace, config, ReplayTransport(entries),
                            base + "/requests.jsonl", base + "/run.jsonl", keep)
        for line in console:
            print(line)
        for line in read_text(base + "/run.jsonl").splitlines():
            event = scrub(json.loads(line), workspace)
            if isinstance(event, dict):
                kind = event.get("event")
                if isinstance(kind, str) and kind not in QUIET_EVENTS:
                    event.pop("ts", None)
                    print(json.dumps(event, sort_keys=True))
        requests = read_text(base + "/requests.jsonl").splitlines()
        print("requests:", len(requests))
        for line in requests:
            request = json.loads(line)
            if isinstance(request, dict):
                body = request.get("body")
                if isinstance(body, dict):
                    messages = body.get("messages")
                    print(" ", body.get("max_tokens"), "tools" in body,
                          len(messages) if isinstance(messages, list) else -1, request.get("timeout"))
        print("status", result["status"], json.dumps(scrub(result["outcome"], workspace), sort_keys=True))
        metadata = result["config"]
        if isinstance(metadata, dict):
            print("config", metadata["config_hash"], metadata["step_policy"],
                  metadata["final_validate"])
        state = result["state"]
        if isinstance(state, dict):
            for key in ("completed_tasks", "errors", "validation_attempts", "pending_empty_writes"):
                print(key, json.dumps(scrub(state[key], workspace), sort_keys=True))
            steps = state["all_steps"]
            if isinstance(steps, list):
                for step in steps:
                    print("step", json.dumps(scrub(step, workspace), sort_keys=True))
        for name in sorted(os.listdir(workspace)):
            path = workspace + "/" + name
            if os.path.isfile(path):
                print("file", name, json.dumps(read_text(path)))
    finally:
        remove_tree(base)


for sample in (b"", b"abc", b"a" * 119):
    print(sha256_pure(sample), sha256_pure(sample) == sha256_hex(sample))

play("write and finish", "Create hello.txt containing hello", {},
     [text('{"tasks": ["Create hello.txt containing hello"]}'),
      tool("write", '{"arg": "hello.txt", "content": "hello\\n"}'),
      tool("done", "{}")])

play("compile repair", "Compile main.c with sh cc.sh and fix any build error",
     {"cc.sh": FAKE_CC, "main.c": 'int main(void) {\n    printf("hi\\n");\n    return 0;\n}\n'},
     [text('{"tasks": ["Build main.c with sh cc.sh main.c", "Add #include <stdio.h> to main.c"]}'),
      tool("shell", '{"arg": "sh cc.sh main.c"}'),
      tool("done", '{"reasoning": "built"}')])

play("navigate, edit and validate", "Correct the total helper so the sum is positive",
     {"src/util.py": "def total(values):\n    result = 0\n    for value in values:\n"
                     "        result -= value\n    return result\n",
      "notes.txt": "caf\u00e9 \u2713\n" * 40},
     [text('```json\n{"tasks": ["Correct total in src/util.py"],}\n```'),
      tool("tree", "{}"),
      tool("search", '{"arg": "result", "path": "src"}'),
      tool("read", '{"arg": "notes.txt", "limit": 30}'),
      tool("read", '{"arg": "src/util.py"}'),
      tool("read", '{"arg": "src/util.py"}'),
      tool("edit", '{"arg": "src/util.py", "find": "result -= value", "replace": "result += value"}'),
      tool("done", "{}"),
      tool("shell", '{"arg": "grep -c \\"result += value\\" src/util.py"}'),
      tool("done", "{}"),
      text('{"valid": false, "reason": "not exercised", "missing": ["a run"]}'),
      text('{"tasks": ["Exercise src/util.py"]}'),
      tool("shell", '{"arg": "grep -c total src/util.py"}'),
      tool("done", "{}"),
      text('{"valid": true}')],
     "lifecycle", "always")

play("retries, a partial write and exhaustion", "Record three lines", {},
     ['{"askme_replay": {"status": 503, "text": "busy"}}',
      '{"askme_replay": {"transport_error": "connection reset by peer"}}',
      text("not json"),
      text('{"tasks": ["Write log.txt"]}'),
      '{"error": {"message": "rate limited", "code": 429}}',
      tool("write", '{"arg": "log.txt", "content": "cut'),
      tool("launch", '{"arg": "rocket"}'),
      text('{"task": "Record three lines in log.txt"}'),
      '{"askme_replay": {"content_truncated": true, "body": '
      + tool("write", '{"arg": "log.txt", "content": "one\\ntwo\\nthr"}') + "}}",
      tool("done", "{}"),
      tool("fail", '{"reasoning": "cannot finish"}')])
