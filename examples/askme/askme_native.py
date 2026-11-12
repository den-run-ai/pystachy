#!/usr/bin/env python3
"""AskMe as one typed program: plans, executes, replans on failure.

This is the ``askme.py`` command line over the typed modules in this
directory. The same files run on CPython and PyPy, compile with mypyc, and
build into a standalone executable with Pystachy. Model inference stays in an
external OpenAI-compatible server; this is not a sandbox.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Callable

from native_host import Host, HttpReply, append_text, path_str, read_text, utc_clock, write_text
from native_json import JSONValue, dumps_pretty, get_flag, get_int, get_str, str_items
from native_llm import (
    REASONING_POLICIES,
    LLMClient,
    get_capability_profile,
    ignore_sleep,
    never_truncated,
    settings_from_env,
)
from native_loop import (
    GOAL_CONTEXT_CHARS,
    RunConfig,
    RunController,
    resolve_workspace,
)
from native_policies import STEP_POLICY_NAMES

# Terminal statuses under which every planned task finished.
# "complete_unverified" marks a completed run whose wanted final validation
# produced no verdict: completion stands, but it is never reported as a
# verified pass. "exhausted" is the only failure status.
COMPLETE_STATUSES = ("complete", "complete_unverified")


def log(msg: str) -> None:
    """Timestamped (UTC) console line for real-time monitoring."""
    sys.stdout.write(f"[{utc_clock(time.time())}] {msg}\n")
    sys.stdout.flush()


def wall_clock() -> float:
    return time.time()


def real_sleep(seconds: float) -> None:
    time.sleep(seconds)


def load_env_file(path: str) -> None:
    """Load ``KEY=VALUE`` lines; variables that are already set win."""
    for raw in read_text(path).splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            pair = line.split("=", 1)
            key = pair[0].strip()
            if key and key not in os.environ:
                os.environ[key] = pair[1].strip()


class UsageError(Exception):
    """A command-line or configuration error; the process exits with status 2."""


class ReplayTransport:
    """Recorded responses in place of a model server.

    The file is a JSON array with one entry per HTTP attempt, or an object
    whose ``replay`` member is that array. An object entry is a 200 reply with
    that body. An entry of the form
    ``{"askme_replay": {...}}`` controls the attempt instead: ``status`` and
    ``text`` or ``body`` give an arbitrary HTTP reply, ``transport_error``
    simulates a failed connection, and ``content_truncated`` marks the write
    in ``body`` as a trusted partial payload.
    """

    def __init__(self, entries: list[JSONValue]) -> None:
        self.entries = entries
        self.position = 0
        self.truncated = False

    def post(self, api: str, body: str, headers: list[str], timeout: int) -> HttpReply:
        self.truncated = False
        if self.position >= len(self.entries):
            return HttpReply(0, "", "replay exhausted")
        entry = self.entries[self.position]
        self.position += 1
        if isinstance(entry, dict):
            control = entry.get("askme_replay")
            if isinstance(control, dict):
                if "transport_error" in control:
                    return HttpReply(0, "", get_str(control, "transport_error"))
                self.truncated = get_flag(control, "content_truncated")
                if "text" in control:
                    text = get_str(control, "text")
                else:
                    text = json.dumps(control.get("body"))
                return HttpReply(get_int(control, "status", 200), text, "")
        return HttpReply(200, json.dumps(entry), "")


def load_replay(path: str) -> ReplayTransport:
    try:
        document = json.loads(read_text(path))
    except OSError as read_error:
        raise UsageError(f"cannot read --replay: {read_error}") from None
    except ValueError as parse_error:
        raise UsageError(f"--replay is not valid JSON: {parse_error}") from None
    if isinstance(document, dict):
        # A scenario file keeps its replies beside the prompt and fixtures.
        document = document.get("replay")
    if not isinstance(document, list):
        raise UsageError("--replay must hold a JSON array of responses")
    return ReplayTransport(document)


def config_from_env(
    reasoning_policy: str | None,
    capability_profile: str | None,
    max_replans: int,
    max_tasks: int,
    max_steps: int,
    goal_context_chars: int | None,
) -> RunConfig:
    """Immutable per-run configuration from the environment; arguments win."""
    policy = os.environ.get("AGENT_REASONING_POLICY", "gated").strip().lower()
    if policy not in REASONING_POLICIES:
        raise ValueError(f"AGENT_REASONING_POLICY must be one of {', '.join(REASONING_POLICIES)}")
    step_policy = os.environ.get("AGENT_STEP_POLICY", "heuristic").strip().lower()
    if step_policy not in STEP_POLICY_NAMES:
        raise ValueError(f"AGENT_STEP_POLICY must be one of {', '.join(STEP_POLICY_NAMES)}")
    llm = settings_from_env()
    if capability_profile is not None:
        llm = llm.with_profile(get_capability_profile(capability_profile))
    goal_chars = GOAL_CONTEXT_CHARS
    raw_goal_chars = os.environ.get("AGENT_GOAL_CONTEXT_CHARS", "")
    if raw_goal_chars:
        goal_chars = int(raw_goal_chars)
    if goal_context_chars is not None:
        goal_chars = goal_context_chars
    return RunConfig(
        llm,
        os.environ.get("ALLOW_SYSTEM_INSTALLS", "0") == "1",
        os.environ.get("ALLOW_NETWORK", "1") == "1",
        policy if reasoning_policy is None else reasoning_policy,
        max_replans,
        max_tasks,
        max_steps,
        goal_chars,
        os.environ.get("AGENT_FINAL_VALIDATE", "auto"),
        os.environ.get("AGENT_COMPILE_REPAIR", "1") == "1",
        step_policy,
    )


def run_result(
    user_prompt: str,
    working_dir: str | None,
    cfg: RunConfig,
    replay: ReplayTransport | None,
    request_log: str,
    run_log_path: str,
    log_sink: Callable[[str], None],
) -> dict[str, JSONValue]:
    """One structured run.

    Resolves the workspace (creating an isolated temporary directory when
    ``working_dir`` is None), composes the controller, and returns the
    structured result: ``status``, ``state`` and ``log``, plus the resolved
    ``config`` metadata (never credentials) and the ``workspace`` ownership
    record.
    """
    workspace = resolve_workspace(working_dir)
    host = Host()
    transport_problem = host.http.mode_problem()
    if transport_problem:
        workspace.cleanup()
        raise UsageError(transport_problem)

    def run_log(event: dict[str, JSONValue]) -> None:
        """Append one JSON event to AGENT_RUN_LOG. Never fails the run."""
        if not run_log_path:
            return
        record: dict[str, JSONValue] = {"ts": time.time()}
        record.update(event)
        try:
            append_text(run_log_path, json.dumps(record) + "\n")
        except OSError:
            pass

    def send(api: str, body: str, headers: list[str], timeout: int) -> HttpReply:
        if request_log:
            # Header names only: a credential never reaches the log.
            names = [header.split(":", 1)[0] for header in headers]
            append_text(
                request_log,
                '{"api": '
                + json.dumps(api)
                + ', "timeout": '
                + str(timeout)
                + ', "headers": '
                + json.dumps(str_items(names))
                + ', "body": '
                + body
                + "}\n",
            )
        if replay is not None:
            return replay.post(api, body, headers, timeout)
        return host.http_post(api, body, headers, timeout)

    def truncated() -> bool:
        return replay is not None and replay.truncated

    sleep: Callable[[float], None] = ignore_sleep if replay is not None else real_sleep
    probe: Callable[[], bool] = truncated if replay is not None else never_truncated
    try:
        try:
            client = LLMClient(cfg.llm, send, sleep, log_sink, run_log, probe)
            controller = RunController(
                user_prompt, workspace.path, cfg, client, host, wall_clock, log_sink, run_log
            )
        except ValueError as invalid:
            # Invalid configuration must not leak an undisclosed temporary
            # directory; cleanup never touches a supplied one.
            workspace.cleanup()
            raise UsageError(str(invalid)) from None
        result = controller.run()
        result["config"] = controller.config_metadata()
        result["workspace"] = workspace.describe()
        return result
    finally:
        host.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="askme",
        description="Run AskMe against an isolated or existing working directory.",
    )
    parser.add_argument("prompt", nargs="?", help="Task request")
    parser.add_argument("--prompt-file", help="Read the task request from this file")
    parser.add_argument("--working-dir", help="Existing workspace for the agent")
    parser.add_argument("--result-json", help="Write the structured run result here")
    parser.add_argument(
        "--reasoning-policy",
        choices=["gated", "off"],
        help="Explicit-reasoning policy (default: AGENT_REASONING_POLICY or gated)",
    )
    parser.add_argument(
        "--capability-profile",
        choices=["generic-feature-scale-v1", "legacy-e4b-m1-16k-v1"],
        help="Model-facing budget/context profile "
        "(default: LLM_CAPABILITY_PROFILE or generic-feature-scale-v1)",
    )
    parser.add_argument(
        "--max-replans",
        type=int,
        default=3,
        help="Maximum planning attempts, including the initial plan",
    )
    parser.add_argument(
        "--max-tasks",
        type=int,
        default=10,
        help="Maximum tasks accepted from each plan",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=10,
        help="Maximum executor steps per task attempt",
    )
    parser.add_argument(
        "--goal-context-chars",
        type=int,
        help="Goal characters available to executor and task replanner "
        "(default: AGENT_GOAL_CONTEXT_CHARS or 300)",
    )
    parser.add_argument("--env-file", help="Load KEY=VALUE settings that are not already set")
    parser.add_argument("--replay", help="Answer model requests from this JSON array of replies")
    parser.add_argument("--request-log", help="Append every model request to this JSONL file")
    args = parser.parse_args()
    # Copy the optional arguments to locals so each test narrows its value.
    env_file: str | None = args.env_file
    prompt: str | None = args.prompt
    prompt_file: str | None = args.prompt_file
    requested_dir: str | None = args.working_dir
    result_json: str | None = args.result_json
    replay_path: str | None = args.replay
    request_log: str | None = args.request_log
    reasoning_policy: str | None = args.reasoning_policy
    capability_profile: str | None = args.capability_profile
    goal_context_chars: int | None = args.goal_context_chars
    max_replans: int = args.max_replans
    max_tasks: int = args.max_tasks
    max_steps: int = args.max_steps

    status = ""
    try:
        if env_file is not None:
            try:
                load_env_file(env_file)
            except (OSError, UnicodeDecodeError) as env_error:
                raise UsageError(f"cannot read --env-file: {env_error}") from None
        if (prompt is None) == (prompt_file is None):
            raise UsageError("provide exactly one of prompt or --prompt-file")
        user_prompt = ""
        if prompt_file is not None:
            try:
                user_prompt = read_text(prompt_file)
            except (OSError, UnicodeDecodeError) as prompt_error:
                raise UsageError(f"cannot read --prompt-file: {prompt_error}") from None
        elif prompt is not None:
            user_prompt = prompt
        if not user_prompt.strip():
            raise UsageError("prompt must not be empty")
        if max_replans < 1:
            raise UsageError("argument --max-replans: must be a positive integer")
        if max_tasks < 1:
            raise UsageError("argument --max-tasks: must be a positive integer")
        if max_steps < 1:
            raise UsageError("argument --max-steps: must be a positive integer")
        if goal_context_chars is not None and goal_context_chars < 1:
            raise UsageError("argument --goal-context-chars: must be a positive integer")
        working_dir: str | None = None  # run_result creates and records an isolated workspace
        if requested_dir is not None:
            if not os.path.isdir(requested_dir):
                raise UsageError("--working-dir must name an existing directory")
            working_dir = path_str(requested_dir)
        replay: ReplayTransport | None = None
        if replay_path is not None:
            replay = load_replay(replay_path)
        try:
            # Immutable per-run configuration loaded from the environment at
            # the CLI boundary; parsed arguments override policy and budgets.
            config = config_from_env(
                reasoning_policy,
                capability_profile,
                max_replans,
                max_tasks,
                max_steps,
                goal_context_chars,
            )
        except ValueError as config_error:
            raise UsageError(str(config_error)) from None
        result = run_result(
            user_prompt,
            working_dir,
            config,
            replay,
            request_log if request_log is not None else "",
            os.environ.get("AGENT_RUN_LOG", ""),
            log,
        )
        status = get_str(result, "status")
        if result_json is not None:
            try:
                write_text(result_json, dumps_pretty(result) + "\n")
            except OSError as write_error:
                raise UsageError(f"cannot write --result-json: {write_error}") from None
    except UsageError as usage_error:
        sys.stderr.write(f"askme: error: {usage_error}\n")
        return 2
    return 0 if status in COMPLETE_STATUSES else 1


if __name__ == "__main__":
    sys.exit(main())
