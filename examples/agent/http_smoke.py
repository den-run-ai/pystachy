"""Exercise the live HTTP path against a local recorded-response server.

This CPython-only test driver makes no model calls. Pass the executable and
any launcher arguments after ``--``; the agent's live-mode arguments follow.
"""

import argparse
import json
import os
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import cast

EXAMPLE = Path(__file__).resolve().parent
GOAL = "Fix value.txt and verify the correction"
CHECK_COMMAND = "grep -qx fixed value.txt"
MODEL = "recorded-http-smoke"
TOKEN = "synthetic-native-agent-smoke-token"
TOOL_NAMES = {"read", "write", "edit", "run_test", "done", "fail"}


class SmokeServer(HTTPServer):
    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), SmokeHandler)
        self.responses = json.loads((EXAMPLE / "fixtures" / "repair.json").read_text())
        self.requests_seen = 0
        self.errors: list[str] = []


class SmokeHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        # The agent transcript and a final summary are the test's output.
        pass

    def do_POST(self) -> None:
        server = cast(SmokeServer, self.server)
        try:
            assert self.path == "/v1/chat/completions", "unexpected endpoint path"
            assert self.headers.get("Authorization") == "Bearer " + TOKEN, "wrong auth header"
            assert self.headers.get("Content-Type") == "application/json", "wrong content type"
            length = int(self.headers.get("Content-Length", "0"))
            assert 0 < length <= 1_048_576, "request exceeds the test bound"
            body = self.rfile.read(length)
            assert TOKEN.encode() not in body, "API key leaked into request body"
            request = json.loads(body)
            assert request["model"] == MODEL, "wrong requested model"
            tools = request["tools"]
            assert len(tools) == len(TOOL_NAMES), "wrong tool count"
            assert {tool["function"]["name"] for tool in tools} == TOOL_NAMES, "wrong tool names"
            assert all(tool["type"] == "function" for tool in tools), "wrong native tool type"
            assert request["parallel_tool_calls"] is False, "parallel calls must be disabled"
            assert request["tool_choice"] == "auto", "wrong tool choice"
            assert 0 < request["max_tokens"] <= 2048, "wrong generation bound"
            messages = request["messages"]
            assert len(messages) == 2, "wrong message count"
            assert messages[0]["role"] == "system", "missing system contract"
            assert messages[1]["role"] == "user", "missing user state"
            prefix = (
                "GOAL:\n"
                + GOAL
                + "\nVISIBLE CHECK COMMAND:\n"
                + CHECK_COMMAND
                + "\nRECENT RECEIPTS:\n"
            )
            content = messages[1]["content"]
            assert content.startswith(prefix), "goal or visible check omitted from request state"
            history = [json.loads(line) for line in content[len(prefix) :].splitlines()]
            index = server.requests_seen
            assert len(history) == min(index, 4), "recent-receipt window is incorrect"
            assert [item["step"] for item in history] == list(range(max(0, index - 4), index)), (
                "receipt window is out of order"
            )
            for item in history:
                if item["action"] == "read":
                    assert item["path"] == "value.txt", "read receipt lost its file path"
            assert index < len(server.responses), "agent requested too many responses"
            response = json.dumps(server.responses[index]).encode()
            server.requests_seen += 1
            self.send_response(200)
        except (AssertionError, KeyError, TypeError, ValueError) as exc:
            server.errors.append(str(exc))
            response = b'{"error":"HTTP smoke request failed validation"}'
            self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


def run_smoke(launcher: list[str]) -> None:
    server = SmokeServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="askme-http-smoke-") as directory:
            workspace = Path(directory)
            (workspace / "value.txt").write_bytes((EXAMPLE / "fixtures" / "value.txt").read_bytes())
            endpoint = "http://127.0.0.1:" + str(server.server_port) + "/v1/chat/completions"
            environment = dict(os.environ)
            environment.update(
                NATIVE_AGENT_ENDPOINT=endpoint,
                NATIVE_AGENT_MODEL=MODEL,
                NATIVE_AGENT_API_KEY=TOKEN,
                # A configured machine proxy must not take this local request away.
                NO_PROXY="127.0.0.1",
                no_proxy="127.0.0.1",
            )
            result = subprocess.run(
                [*launcher, str(workspace), GOAL, CHECK_COMMAND, "-", "12"],
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert not server.errors, "; ".join(server.errors)
            assert TOKEN not in result.stdout + result.stderr, "API key leaked into agent output"
            assert not result.stderr, "unexpected agent stderr: " + result.stderr
            assert result.returncode == 0, "agent failed:\n" + result.stdout
            events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            assert events[-1] == {"event": "result", "status": "complete"}, "missing completion"
            assert [item["action"] for item in events[:-1]] == [
                "done",
                "read",
                "edit",
                "run_test",
                "done",
            ], "wrong repair sequence"
            assert events[0]["ok"] is False, "early completion was accepted"
            assert events[-2]["ok"] is True, "checked completion was refused"
            assert server.requests_seen == len(server.responses), "fixture was not fully consumed"
            assert (workspace / "value.txt").read_bytes() == b"fixed\n", "wrong repaired bytes"
            assert sorted(path.name for path in workspace.iterdir()) == ["value.txt"], (
                "unexpected workspace artifacts"
            )
            print(result.stdout, end="")
            print(
                "HTTP smoke passed: "
                + str(server.requests_seen)
                + " validated requests; checked repair; launcher="
                + " ".join(launcher)
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive(), "HTTP server thread did not stop"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "launcher", nargs=argparse.REMAINDER, help="executable and launcher arguments"
    )
    arguments = parser.parse_args()
    launcher = arguments.launcher
    if launcher and launcher[0] == "--":
        launcher = launcher[1:]
    if not launcher:
        parser.error("supply an executable, for example: -- python3 examples/native_agent/agent.py")
    run_smoke(launcher)


if __name__ == "__main__":
    main()
