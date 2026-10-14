"""Typed native-tool agent: repair, verification gates, and strict Unicode JSON."""
import os
import tempfile

from agent import decode_action, run_agent, shell_quote, shell_status
from wire_json import JsonDocument, json_quote, utf8_size


def reply(kind: str, arguments: str) -> str:
    return ('{"choices":[{"message":{"tool_calls":[{"type":"function","function":'
            '{"name":' + json_quote(kind) + ',"arguments":' + json_quote(arguments) + '}}]}}]}')


def replay(workspace: str, responses: list[str], steps: int) -> str:
    path = workspace + "/responses.json"
    with open(path, "w", encoding="utf-8", newline="") as stream:
        stream.write("[" + ",".join(responses) + "]")
    return run_agent(workspace, "Fix value.txt", "grep -qx fixed value.txt", path, steps)


work = tempfile.mkdtemp()
try:
    with open(work + "/value.txt", "w", encoding="utf-8", newline="") as stream:
        stream.write("wrong\n")
    print(replay(work, [reply("done", "{}"), reply("read", '{"path":"value.txt"}'),
                       reply("edit", '{"path":"value.txt","old":"wrong","new":"fixed"}'),
                       reply("run_test", "{}"), reply("done", "{}")], 8))
    with open(work + "/value.txt", "r", encoding="utf-8", newline="") as stream:
        print(stream.read() == "fixed\n")
    # An edit after a successful test invalidates completion evidence.
    print(replay(work, [reply("run_test", "{}"),
                       reply("edit", '{"path":"value.txt","old":"fixed","new":"wrong"}'),
                       reply("done", "{}")], 3))
    print(replay(work, [reply("run_test", "{}"), reply("done", "{}")], 2))
    # Content-only replies and malformed arguments cannot become actions.
    for invalid in ['{"choices":[{"message":{"content":"done"}}]}',
                    reply("write", '{"path":"new.txt","content":"unfinished'),
                    reply("edit", '{"path":"value.txt","old":"","new":"x"}'),
                    reply("shell", '{"command":"true"}')]:
        try:
            decode_action(invalid)
            print("accepted invalid")
        except ValueError:
            print("rejected")
    document = JsonDocument('{"value":"caf\\u00e9 \\ud83d\\ude00", "n":-2.5e+3}')
    value = document.string(document.field(document.root, "value"))
    print(value, utf8_size(value), json_quote(value))
    print(document.raw(document.field(document.root, "n")))
    for invalid in ['{"key":1,"key":2}', '[0,]', '"\\ud800"', '1e', '{} trailing']:
        try:
            JsonDocument(invalid)
            print("accepted invalid")
        except ValueError:
            print("rejected")
finally:
    shell_status("rm -rf -- " + shell_quote(work))
