"""Planning, prompt builders and controller sequencing (mirrors ``loop.py``).

The runtime consumes one resolved :class:`RunConfig` and explicit
collaborators. This module never reads the environment or loads ``.env``;
the CLI resolves configuration before a run starts.
"""

from __future__ import annotations

import json
import os
import re
import shlex
from typing import Callable

from native_actions import (
    OBSERVE_ACTIONS,
    OBSERVE_STATE_CHARS,
    ActionExecutor,
    ActionResult,
    _mutation_target_key,
    _step_path,
    receipt_deterministic_repair,
    receipt_deterministic_retry,
    receipt_executed,
)
from native_host import (
    Host,
    make_workspace,
    path_is_absolute,
    path_join,
    path_name,
    path_relative_to,
    path_resolve,
    path_str,
    read_text,
    remove_tree,
    sha256_hex,
)
from native_json import (
    JSONValue,
    as_dict,
    as_str,
    copy_dict,
    get_dict,
    get_flag,
    get_int,
    get_list,
    get_str,
    str_items,
    truthy,
)
from native_llm import (
    ACTION_TRANSPORT,
    REASONING_POLICIES,
    LLMApiError,
    LLMClient,
    LLMSettings,
    LLMTransportError,
    ReplyDecodeError,
    parse_plan,
    parse_task_replan,
    parse_validation,
)
from native_policies import (
    _VALIDATE_KEYWORDS,
    FLOW_DISPATCH,
    FLOW_END_ATTEMPT,
    FLOW_NEXT_STEP,
    STEP_POLICY_NAMES,
    CompletionContext,
    CompletionPolicy,
    CompletionVerdict,
    PolicyServices,
    RunOutcome,
    StepPolicy,
    WriteObligations,
    _incomplete_write_visibility,
    _unresolved_incomplete_writes,
    _write_visibility_flag,
    make_step_policy,
)
from native_state import (
    REWRITE_PRESSURE_WRITES,
    REWRITE_SKIP_WRITES,
    WRITE_PRESSURE_OBSERVATIONS,
    RunProgress,
    RunState,
    StepContext,
    StepRecorder,
    TaskAttemptState,
    json_list,
)

MAX_REPLANS = 3
MAX_TASKS = 10
MAX_STEPS = 10
MAX_STEP_HISTORY = 3
MAX_INPUT = 300
GOAL_CONTEXT_CHARS = 300
DEFAULT_REASONING_POLICY = "gated"
OBSERVE_TAIL_RESERVE = 3
MAX_TASK_LOCAL_REPLANS = 1

PROBE_TOOLS = ["python3", "go", "node", "gcc", "cc", "make", "cargo", "rustc", "java", "javac"]

PROBE_PKG_MANAGERS = ["brew", "apt-get", "dnf", "pacman", "apk"]

_WRITE_TASK_RE = re.compile(
    r"\b(implement|write|create|patch|add|fix|edit|update|replace|insert)\b",
    re.I,
)

_OBSERVE_TASK_RE = re.compile(
    r"^\s*(find|search|locate|inspect|read|list|review|explore|examine|look|check|show)\b",
    re.I,
)

SYSTEM_PLAN = f"""Planner. Propose tasks for the user request.
Rules:
- Prefer 1-3 tasks, max {MAX_TASKS}; each is a complete goal, not one command
- Short tasks (<15 words) with key details: includes, imports, filenames
- Relative filenames only, except preserve an exact incomplete_write_target
  supplied in state. Match state.environment.platform
- Never redo completed_tasks
- If required tool in missing_tools and allow_system_installs=false: single prerequisite/fail task listing missing tools
- If allow_system_installs=true: may use package_managers
Output ONLY valid JSON. No markdown, no explanation.
Format: {{"tasks":["task1","task2"]}}"""

SYSTEM_STEP = """Executor. Call exactly ONE tool per turn. No text outside the tool call.
Rules:
- done only when the FULL task description is satisfied
- fail if same error appears 2+ times
- Never redo completed_tasks
- Relative paths, except use an exact incomplete_write_target supplied in state.
  Recover it before done; append only when incomplete_write_append_allowed=true.
  Reasoning max 10 words
- If missing_tools required and allow_system_installs=false: fail; do NOT install
- Prefer edit over write for existing files
- Prefer search/tree over shell grep/find/ls
- read: initial pages take offset/limit (1-based lines); continuation pages must
  echo the output's cursor, limit, and sha256. Cursors count Unicode code points.
- write: whole file in content; set append=true to append the next chunk"""

SYSTEM_VALIDATE = """You are a completion validator. Given a goal, completed tasks with their execution evidence, and the current working directory listing, determine if the goal was fully achieved.

Examine the evidence carefully:
- Did all required files get created?
- Did compilation/build succeed?
- Did the program run and produce correct output?
- Were all parts of the goal addressed?

Output ONLY valid JSON. No markdown, no explanation.
Format: {"valid": true} or {"valid": false, "reason": "what is missing or wrong", "missing": ["specific missing items"]}"""

SYSTEM_TASK_REPLAN = """You are a task replanner. A single task failed. Given the failed task, errors, and completed tasks, propose a replacement task description.
Do NOT repeat completed work. The replacement must address the failure.
Preserve the original task's outcome. If it was to fix, edit, add, compile, run, create, or write something, do NOT replace it with a read/list/inspect-only preparation task.
Keep the replacement short (under 15 words). Use relative filenames, except
preserve an exact incomplete_write_target supplied in state.
Output ONLY valid JSON. No markdown, no explanation.
Format: {"task": "replacement task description"}"""

_KNOWN_ERROR_TYPES = frozenset(
    {
        "timeout",
        "missing_tool",
        "permission_denied",
        "missing_file",
        "compile_error",
        "edit_failed",
        "stuck_loop",
        "unknown",
        "unknown_action",
        "control_action",
        "malformed_action",
        "response_truncated",
        "invalid_read_cursor",
        "invalid_read_limit",
        "invalid_read_offset",
        "invalid_timeout",
        "read_cursor_hash_required",
        "stale_read_cursor",
    }
)

_NO_THINK_ERRORS = frozenset(
    {
        "edit_failed",
        "missing_file",
        "timeout",
        "missing_tool",
        "permission_denied",
        "invalid_read_cursor",
        "invalid_read_limit",
        "invalid_read_offset",
        "invalid_timeout",
        "read_cursor_hash_required",
        "stale_read_cursor",
    }
)

_RECOVERY_HINTS = {
    "edit_failed": "Read the file first, then retry edit with exact text from the file.",
    "missing_file": "Check the filename. Use shell ls to list directory contents.",
    "invalid_read_cursor": "Use cursor, limit, and sha256 exactly from the latest read continuation.",
    "invalid_read_limit": "Use cursor, limit, and sha256 exactly from the latest read continuation.",
    "invalid_read_offset": "Use a positive integer offset within the supported range.",
    "invalid_timeout": "Use an integer timeout from 5 to 300 seconds.",
    "read_cursor_hash_required": "Use cursor, limit, and sha256 exactly from the latest read continuation.",
    "stale_read_cursor": "The file changed. Restart read with offset and limit; do not reuse the old cursor.",
}

_PASSIVE_TASK_RE = re.compile(r"^\s*(read|inspect|view|open|list|check|examine)\b", re.I)

_ACTION_TASK_RE = re.compile(
    r"\b(fix|edit|add|insert|include|compile|build|run|create|write|update|replace|execute|remove)\b",
    re.I,
)

_PASSIVE_THEN_ACTION_RE = re.compile(
    r"\b(then|and)\b.*\b(fix|edit|add|insert|include|compile|build|run|create|write|update|replace|execute|remove)\b",
    re.I,
)

_LOW_VALUE_TASK_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "again",
        "code",
        "correct",
        "file",
        "for",
        "in",
        "of",
        "rebuild",
        "recompile",
        "rerun",
        "run",
        "the",
        "then",
        "to",
        "using",
        "with",
    }
)

_EDIT_LIKE_WORDS = frozenset(
    {"fix", "edit", "add", "insert", "include", "update", "replace", "write"}
)

_TASK_WORD_RE = re.compile(r"[a-z0-9_.]+")
_TASK_ENTITY_RE = re.compile(r"\b[a-z0-9_./-]+\.(?:c|h|py|txt|json|md|js|ts|go|rs|java)\b")
_DIAGNOSTIC_PATH_RE = re.compile(r"([A-Za-z0-9_./-]+\.(?:c|h)):\d+(?::\d+)?:")
_INCLUDE_TASK_RE = re.compile(r"\b(add|insert|edit|include|fix)\b")
_C_SOURCE_RE = re.compile(r"\.(c|h)$")

_STDIO_DIAGNOSTIC_RE = re.compile(
    r"implicit declaration of function '(printf|puts|fprintf|scanf)'|"
    r"implicitly declaring library function '(printf|puts|fprintf|scanf)'|"
    r"undeclared library function '(printf|puts|fprintf|scanf)'|"
    r"include the header <stdio\.h>|"
    r"stdio\.h.*[Nn]o such file",
    re.I,
)
_STRING_DIAGNOSTIC_RE = re.compile(
    r"implicit declaration of function '(strlen|strcmp|strcpy|strcat|memcpy)'|"
    r"undeclared library function '(strlen|strcmp|strcpy|strcat|memcpy)'|"
    r"include the header <string\.h>|"
    r"string\.h.*[Nn]o such file",
    re.I,
)


def _is_write_shaped(task: str) -> bool:
    return (
        bool(task)
        and _WRITE_TASK_RE.search(task) is not None
        and _OBSERVE_TASK_RE.match(task) is None
    )


def _extract_error_type(err: str) -> tuple[str, str]:
    """Extract [type] prefix from error string if present, else classify by heuristic."""
    # Check for existing [type] prefix from classify_error / run loop
    if err.startswith("["):
        bracket_end = err.find("]")
        if bracket_end > 1:
            candidate = err[1:bracket_end]
            if candidate in _KNOWN_ERROR_TYPES:
                return candidate, err[bracket_end + 2 :]  # strip "[type] " prefix
    # Fallback: heuristic classification
    err_lower = err.lower()
    if "timeout" in err_lower:
        return "timeout", err
    if "command not found" in err_lower:
        return "missing_tool", err
    if "permission denied" in err_lower:
        return "permission_denied", err
    if "no such file" in err_lower:
        return "missing_file", err
    if "stuck" in err_lower or "failed twice" in err_lower:
        return "stuck_loop", err
    if "error:" in err_lower or "syntax error" in err_lower:
        return "compile_error", err
    return "unknown", err


def summarize_errors(errors: list[JSONValue]) -> list[JSONValue]:
    """Compact error strings into typed summary for planner.
    Preserves [type] prefixes from classify_error, groups by type, deduplicates."""
    result: list[JSONValue] = []
    if not errors:
        return result
    summarized: dict[str, list[str]] = {}
    for item in errors:
        etype, msg = _extract_error_type(as_str(item))
        if etype not in summarized:
            summarized[etype] = []
        short = msg[:120]
        if short not in summarized[etype]:
            summarized[etype].append(short)
    for etype, msgs in summarized.items():
        for msg in msgs[:3]:  # max 3 per type
            result.append(f"[{etype}] {msg}")
    return result


def _step_digest(steps: list[JSONValue], count: int = 6) -> list[JSONValue]:
    """Compact digest of recent executed steps for planning (never file contents)."""
    digest: list[JSONValue] = []
    for item in steps[-count:]:
        s = as_dict(item)
        entry: dict[str, JSONValue] = {
            "action": s.get("action"),
            "arg": get_str(s, "arg")[-120:],
            "ok": s.get("ok"),
            "output": get_str(s, "output")[:80],
        }
        digest.append(entry)
    return digest


class TaskReplanResult:
    """Structured task-local replan outcome.

    ``task`` is the accepted replacement, or empty when the replan failed;
    ``reject_reason`` then carries the typed reason."""

    def __init__(self, task: str, reject_reason: str) -> None:
        self.task = task
        self.reject_reason = reject_reason


def _task_keywords(text: str) -> set[str]:
    """Normalized content words for rejecting near-duplicate task replans."""
    text = text.lower().replace("#include", "include")
    words = _TASK_WORD_RE.findall(text)
    return {w for w in words if len(w) > 1 and w not in _LOW_VALUE_TASK_WORDS}


def _task_entities(text: str) -> set[str]:
    """Extract concrete files/headers mentioned in a task."""
    text = text.lower().replace("#include", "include")
    return set(_TASK_ENTITY_RE.findall(text))


def _task_action_words(text: str) -> list[str]:
    """Normalized action words that define the kind of task."""
    return _ACTION_TASK_RE.findall(text.lower())


def _is_near_duplicate_task(original: str, replacement: str) -> bool:
    """True when a replacement only rephrases or appends low-value words."""
    orig = _task_keywords(original)
    repl = _task_keywords(replacement)
    if not orig or not repl:
        return False
    orig_entities = _task_entities(original)
    repl_entities = _task_entities(replacement)
    orig_actions = set(_task_action_words(original))
    repl_actions = set(_task_action_words(replacement))
    if orig_entities and orig_entities == repl_entities:
        if orig_actions & _EDIT_LIKE_WORDS and repl_actions & _EDIT_LIKE_WORDS:
            return True
    overlap = len(orig & repl)
    jaccard = overlap / len(orig | repl)
    coverage = overlap / min(len(orig), len(repl))
    return jaccard >= 0.8 or coverage >= 0.9


def _is_passive_replacement(original: str, replacement: str) -> bool:
    """Reject prep-only replacements that downgrade an actionable task."""
    if not _ACTION_TASK_RE.search(original):
        return False
    if not _PASSIVE_TASK_RE.search(replacement):
        return False
    # Allow compact two-part tasks such as "check error and fix include".
    return _PASSIVE_THEN_ACTION_RE.search(replacement) is None


CHECK_PASSED = 1
CHECK_FAILED = 0
CHECK_UNDECIDED = -1


def _deterministic_check(user_prompt: str, state: dict[str, JSONValue], working_dir: str) -> int:
    """Conservative completion check: passed, failed, or undecided."""
    all_steps = get_list(state, "all_steps")
    if truthy(state.get("pending_empty_writes")):
        return CHECK_FAILED

    # A truncated write is an incomplete artifact, not successful completion
    # evidence. Unrelated edits/shells cannot hide it; only a later complete
    # write/append to the same normalized target resolves it.
    if _unresolved_incomplete_writes(all_steps, working_dir):
        return CHECK_FAILED

    # Successful writes should leave non-empty files.
    last_shell_idx = -1
    idx = 0
    for item in all_steps:
        s = as_dict(item)
        if s.get("action") == "write" and get_flag(s, "ok"):
            arg = get_str(s, "arg")
            if not arg.strip():
                return CHECK_FAILED
            p = _step_path(arg, working_dir)
            try:
                if not os.path.exists(p) or os.path.getsize(p) == 0:
                    return CHECK_FAILED
            except OSError:
                return CHECK_FAILED
        if s.get("action") == "shell":
            last_shell_idx = idx
        idx += 1

    if _VALIDATE_KEYWORDS.search(user_prompt) and last_shell_idx >= 0:
        if not get_flag(as_dict(all_steps[last_shell_idx]), "ok"):
            return CHECK_FAILED
        later_mutation = False
        for item in all_steps[last_shell_idx + 1 :]:
            s = as_dict(item)
            if get_str(s, "action") in ("write", "edit") and get_flag(s, "ok"):
                later_mutation = True
        if not later_mutation and not truthy(state.get("errors")):
            return CHECK_PASSED

    return CHECK_UNDECIDED


def _resolve_existing_candidates(paths: list[str], working_dir: str) -> list[str]:
    resolved: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        p = path_str(raw) if path_is_absolute(raw) else path_join(working_dir, raw)
        key = path_resolve(p)
        if os.path.exists(p) and os.path.isfile(p) and key not in seen:
            seen.add(key)
            resolved.append(p)
    return resolved


def _compile_repair_candidates(error_output: str, cmd: str, working_dir: str) -> list[str]:
    """Return source-file candidates in safest priority order."""
    diagnostic_paths = _DIAGNOSTIC_PATH_RE.findall(error_output)
    diagnostic_candidates = _resolve_existing_candidates(diagnostic_paths, working_dir)
    if diagnostic_candidates:
        return diagnostic_candidates

    try:
        parts = shlex.split(cmd)
    except ValueError:
        parts = cmd.split()
    command_paths: list[str] = []
    skip_next = False
    for part in parts[1:]:
        if skip_next:
            skip_next = False
            continue
        if part == "-o":
            skip_next = True
            continue
        if part.endswith(".c") or part.endswith(".h"):
            command_paths.append(part)
    command_candidates = _resolve_existing_candidates(command_paths, working_dir)
    if command_candidates:
        return command_candidates

    c_files: list[str] = []
    try:
        names = os.listdir(working_dir)
    except OSError:
        return c_files
    for name in sorted(names):
        if name.endswith(".c"):
            c_files.append(path_join(working_dir, name))
    if len(c_files) == 1:
        return c_files
    none: list[str] = []
    return none


def _task_satisfied_by_deterministic_repair(
    task: str, state: dict[str, JSONValue]
) -> dict[str, JSONValue] | None:
    """Return repair step if a planned edit task was already done deterministically."""
    task_lower = task.lower()
    if "include" not in task_lower or not _INCLUDE_TASK_RE.search(task_lower):
        return None
    requested_include = ""
    for include in ("#include <stdio.h>", "#include <string.h>"):
        header = include.split("<", 1)[1].rstrip(">").lower()
        if include.lower() in task_lower or header in task_lower:
            requested_include = include
            break
    if not requested_include:
        return None

    entities = {path_name(e) for e in _task_entities(task)}
    all_steps = get_list(state, "all_steps")
    index = len(all_steps) - 1
    while index >= 0:
        step = as_dict(all_steps[index])
        index -= 1
        if not get_flag(step, "deterministic_repair"):
            continue
        if requested_include not in get_str(step, "output"):
            continue
        arg_name = path_name(get_str(step, "arg"))
        if entities and arg_name not in entities:
            continue
        return copy_dict(step)
    return None


class GuardThresholds:
    """Resolved controller guard thresholds for one run.

    These counters decide when observation must yield to a commit, when
    rewrites must yield to verification, and how many task-local replans an
    attempt gets — outcome-affecting policy, so they are frozen per run and
    enter the hash-logged configuration."""

    def __init__(
        self,
        write_pressure_observations: int,
        observe_tail_reserve: int,
        rewrite_pressure_writes: int,
        rewrite_skip_writes: int,
        max_task_local_replans: int,
    ) -> None:
        if write_pressure_observations < 0:
            raise ValueError("write_pressure_observations must be a non-negative integer")
        if observe_tail_reserve < 0:
            raise ValueError("observe_tail_reserve must be a non-negative integer")
        if rewrite_pressure_writes < 0:
            raise ValueError("rewrite_pressure_writes must be a non-negative integer")
        if rewrite_skip_writes < 0:
            raise ValueError("rewrite_skip_writes must be a non-negative integer")
        if max_task_local_replans < 0:
            raise ValueError("max_task_local_replans must be a non-negative integer")
        self.write_pressure_observations = write_pressure_observations
        self.observe_tail_reserve = observe_tail_reserve
        self.rewrite_pressure_writes = rewrite_pressure_writes
        self.rewrite_skip_writes = rewrite_skip_writes
        self.max_task_local_replans = max_task_local_replans

    def describe(self) -> dict[str, JSONValue]:
        """JSON-ready threshold record for config metadata and hashing."""
        record: dict[str, JSONValue] = {
            "write_pressure_observations": self.write_pressure_observations,
            "observe_tail_reserve": self.observe_tail_reserve,
            "rewrite_pressure_writes": self.rewrite_pressure_writes,
            "rewrite_skip_writes": self.rewrite_skip_writes,
            "max_task_local_replans": self.max_task_local_replans,
        }
        return record


def _config_hash(payload: dict[str, JSONValue]) -> str:
    """Short stable digest of the resolved outcome-affecting configuration.

    Canonical-JSON sha256 prefix; never includes credentials. Two runs with
    the same hash ran the same policy surface."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256_hex(canonical.encode("utf-8"))[:16]


class RunWorkspace:
    """Workspace identity and ownership for one run.

    ``created`` is True only when the run made the temporary directory, so
    callers can clean up intentionally; supplied directories are never
    removed by AskMe."""

    def __init__(self, path: str, created: bool) -> None:
        self.path = path
        self.created = created

    def cleanup(self) -> None:
        """Remove the directory only if this run created it."""
        if self.created:
            remove_tree(self.path)

    def describe(self) -> dict[str, JSONValue]:
        """JSON-ready ownership record for the structured run result."""
        record: dict[str, JSONValue] = {"path": self.path, "created": self.created}
        return record


def resolve_workspace(working_dir: str | None) -> RunWorkspace:
    """Use the caller's directory, or create an isolated temporary one."""
    if working_dir is None:
        return RunWorkspace(make_workspace(), True)
    return RunWorkspace(working_dir, False)


def preflight_probe(working_dir: str, host: Host) -> dict[str, JSONValue]:
    """Deterministic environment probe. Returns structured dict for planner state."""
    probe = host.probe(PROBE_TOOLS + PROBE_PKG_MANAGERS)
    env: dict[str, JSONValue] = {
        "platform": probe.system.lower(),  # "darwin", "linux"
        "arch": probe.machine,  # "arm64", "x86_64"
        "working_dir": path_resolve(working_dir),
    }
    # Available tools (fixed allowlist, no prompt inference)
    available: list[JSONValue] = []
    missing: list[JSONValue] = []
    for tool in PROBE_TOOLS:
        if tool in probe.found:
            available.append(tool)
        else:
            missing.append(tool)
    env["available_tools"] = available
    env["missing_tools"] = missing
    # Package managers
    pkg_managers: list[JSONValue] = []
    for pm in PROBE_PKG_MANAGERS:
        if pm in probe.found:
            pkg_managers.append(pm)
    env["package_managers"] = pkg_managers
    # Dir listing (compact)
    try:
        entries = sorted(os.listdir(working_dir))[:20]
        env["dir_listing"] = str_items(entries if entries else ["(empty)"])
    except OSError:
        env["dir_listing"] = str_items(["(error reading dir)"])
    return env


def _message(role: str, content: str) -> dict[str, JSONValue]:
    message: dict[str, JSONValue] = {"role": role, "content": content}
    return message


def _policy_of(state: dict[str, JSONValue], default_policy: dict[str, JSONValue]) -> JSONValue:
    if "policy" in state:
        return state["policy"]
    return default_policy


def get_plan(
    user_prompt: str,
    state: dict[str, JSONValue],
    client: LLMClient,
    default_policy: dict[str, JSONValue],
    max_tokens: int,
    max_tasks: int,
    timeout: int,
    replan_timeout: int,
    max_retries: int,
) -> JSONValue:
    # Include environment and policy in planner state. Run-control metadata is
    # logged/returned but is not task evidence for the model, and raw step
    # payloads (write contents) never reach the planner — only a curated
    # digest does. This keeps replan state bounded on write-heavy runs while
    # still telling the planner what already happened.
    plan_state: dict[str, JSONValue] = {}
    for key in ("completed_tasks", "errors", "environment", "policy"):
        if key in state:
            plan_state[key] = state[key]
    all_steps = get_list(state, "all_steps")
    recent = _step_digest(all_steps)
    if recent:
        plan_state["recent_steps"] = recent
    # Write-forcing visibility: make the actual write state visible instead of
    # letting a replan restate the failed task. Incomplete artifacts are
    # run-scoped completion blockers; no_write/unvalidated progress remains
    # scoped to, and classified from, the failed task itself.
    task_steps = all_steps[get_int(state, "task_start_step_count", 0) :]
    current_task = get_str(state, "current_task")
    incomplete = _incomplete_write_visibility(all_steps, get_dict(state, "pending_empty_writes"))
    if incomplete is not None:
        plan_state.update(incomplete)
    elif _is_write_shaped(current_task):
        flag = _write_visibility_flag(task_steps)
        if flag is not None:
            plan_state.update(flag)
    if "environment" not in plan_state:
        no_environment: dict[str, JSONValue] = {}
        plan_state["environment"] = no_environment
    if "policy" not in plan_state:
        plan_state["policy"] = default_policy
    # Summarize errors for compact, typed diagnostics
    if truthy(plan_state.get("errors")):
        plan_state["errors"] = summarize_errors(get_list(plan_state, "errors"))
    # Think on second/later planning attempts (or stateful direct replans) —
    # first plans don't benefit from thinking, and thinking tokens compete with
    # the task-list budget.
    is_replan = (
        get_int(state, "planning_attempt", 0) > 0
        or truthy(plan_state.get("errors"))
        or truthy(plan_state.get("completed_tasks"))
    )
    messages: list[JSONValue] = [
        _message("system", SYSTEM_PLAN),
        _message("user", f"REQUEST:\n{user_prompt}\n\nSTATE:\n{json.dumps(plan_state)}"),
    ]
    decoded = client.ask(
        messages,
        max_tokens,
        is_replan,
        "",
        max_retries,
        replan_timeout if is_replan else timeout,
        get_str(state, "reasoning_policy", DEFAULT_REASONING_POLICY),
        "planner_replan" if is_replan else "initial_plan",
        "plan",
        # The decode-time schema truncates exactly like the consuming call
        # site: the run's task limit, not the module default.
        max_tasks,
    )
    return decoded.obj


def build_step_message(
    task: str,
    state: dict[str, JSONValue],
    default_policy: dict[str, JSONValue],
    goal: str,
    step_num: int,
    max_steps: int,
    goal_context_chars: int,
    write_pressure: bool,
    validate_pressure: str | None,
) -> str:
    """The executor's user message: goal, task and the slim sliding state."""
    # Build slim step history from recent steps (current task + carryover from previous)
    steps = get_list(state, "last_steps")[-MAX_STEP_HISTORY:]
    slim_steps: list[JSONValue] = []
    for item in steps:
        s = as_dict(item)
        action = as_str(s["action"])
        # Use basename for file paths to avoid long tmp_path bloat
        arg = get_str(s, "arg")
        if action in ("write", "read", "edit", "tree") and "/" in arg:
            arg = path_name(arg)
        else:
            arg = arg[-MAX_INPUT:]
        # Observation actions (read/search/tree) carry the content the model
        # navigates by; they get a larger output budget than mutating actions.
        out_cap = OBSERVE_STATE_CHARS if action in OBSERVE_ACTIONS else MAX_INPUT
        slim_step: dict[str, JSONValue] = {
            "action": s["action"],
            "arg": arg,
            "ok": s["ok"],
            "output": get_str(s, "output")[:out_cap],
        }
        slim_steps.append(slim_step)
    slim: dict[str, JSONValue] = {
        "task": get_str(state, "current_task", task)[:MAX_INPUT],
        "task_index": state.get("task_index", ""),
        "step": f"{step_num + 1}/{max_steps}",
        "last_steps": slim_steps,
    }
    incomplete = _incomplete_write_visibility(
        get_list(state, "all_steps"), get_dict(state, "pending_empty_writes")
    )
    if incomplete is not None:
        # Keep the recovery identity/mode structured on every executor turn.
        # Step history is bounded and is reset across a task-local retry.
        slim.update(incomplete)
    # Include completed tasks so executor knows what's already done
    completed = get_list(state, "completed_tasks")
    if completed:
        recent_tasks: list[JSONValue] = []
        for done_task in completed[-3:]:
            recent_tasks.append(as_str(done_task)[:80])
        slim["completed_tasks"] = recent_tasks
    # Include missing tools and policy so executor can fail fast on prerequisites
    env = get_dict(state, "environment")
    if truthy(env.get("missing_tools")):
        slim["missing_tools"] = env["missing_tools"]
    slim["policy"] = _policy_of(state, default_policy)
    goal_line = f"GOAL:\n{goal[:goal_context_chars]}\n\n" if goal else ""
    user_msg = f"{goal_line}TASK:\n{task[:MAX_INPUT]}\n\nSTATE:\n{json.dumps(slim)}"
    if write_pressure:
        user_msg += (
            "\nNOTE: several observation steps done but no write yet. "
            "Next action MUST be write, edit, or shell — or fail with a one-line reason."
        )
    if validate_pressure:
        user_msg += (
            f"\nNOTE: {validate_pressure} is already written. Do NOT write the whole "
            "file again. Next action MUST be shell (verify it), edit (targeted fix), "
            "or done."
        )
    return user_msg


def replan_task(
    failed_task: str,
    errors: list[JSONValue],
    completed_tasks: list[JSONValue],
    state: dict[str, JSONValue],
    user_prompt: str,
    client: LLMClient,
    default_policy: dict[str, JSONValue],
    goal_context_chars: int,
    max_tokens: int,
    timeout: int,
    max_retries: int,
) -> TaskReplanResult:
    """Mini-planner: generate a replacement for one failed task.

    ``task`` is empty when the replan failed and ``reject_reason`` then names
    the typed rejection."""
    recent_tasks: list[JSONValue] = []
    for done_task in completed_tasks[-3:]:
        recent_tasks.append(as_str(done_task)[:80])
    replan_state: dict[str, JSONValue] = {
        "failed_task": failed_task,
        "errors": summarize_errors(errors),
        "completed_tasks": recent_tasks,
    }
    # Stateful replanning: the mini-planner sees what the executor actually did
    # on the failed task (actions + outcomes), not just typed error strings.
    all_steps = get_list(state, "all_steps")
    task_steps = all_steps[get_int(state, "task_start_step_count", 0) :]
    failed_steps = _step_digest(task_steps, 3)
    if failed_steps:
        replan_state["failed_steps"] = failed_steps
    # failed_steps and advisory progress flags remain task-scoped even when
    # the slice is empty. Incomplete artifacts are checked run-wide because
    # they remain a completion blocker across replacement-task boundaries.
    incomplete = _incomplete_write_visibility(all_steps, get_dict(state, "pending_empty_writes"))
    if incomplete is not None:
        replan_state.update(incomplete)
    elif _is_write_shaped(failed_task):
        flag = _write_visibility_flag(task_steps)
        if flag is not None:
            replan_state.update(flag)
    env = get_dict(state, "environment")
    if truthy(env.get("missing_tools")):
        replan_state["missing_tools"] = env["missing_tools"]
    replan_state["policy"] = _policy_of(state, default_policy)
    messages: list[JSONValue] = [
        _message("system", SYSTEM_TASK_REPLAN),
        _message(
            "user",
            f"GOAL:\n{user_prompt[:goal_context_chars]}\n\nSTATE:\n{json.dumps(replan_state)}",
        ),
    ]
    try:
        decoded = client.ask(
            messages,
            max_tokens,
            False,
            "",
            max_retries,
            timeout,
            get_str(state, "reasoning_policy", DEFAULT_REASONING_POLICY),
            "task_local_replan",
            "task_replan",
        )
    except LLMTransportError:
        return TaskReplanResult("", "transport_error")
    except ReplyDecodeError:
        return TaskReplanResult("", "parse_error")
    except LLMApiError:
        return TaskReplanResult("", "missing_task_key")
    parsed = parse_task_replan(decoded.obj)
    if parsed is None:
        return TaskReplanResult("", "empty")
    task = parsed.strip()
    if len(task) <= 3:
        return TaskReplanResult("", "too_short")
    if task == failed_task.strip():
        return TaskReplanResult("", "exact_duplicate")
    if _is_near_duplicate_task(failed_task, task):
        return TaskReplanResult("", "near_duplicate")
    if _is_passive_replacement(failed_task, task):
        return TaskReplanResult("", "passive_downgrade")
    return TaskReplanResult(task, "")


def _validate_completion(
    user_prompt: str,
    state: dict[str, JSONValue],
    working_dir: str,
    client: LLMClient,
    emit: Callable[[str], None],
    max_tokens: int,
    timeout: int,
    max_retries: int,
) -> CompletionVerdict | None:
    """Run final validation. Returns a verdict or None.

    None means no verdict was available — the validator was unreachable or
    replied outside its schema. Callers must treat that as unverified, never
    as a pass."""
    deterministic = _deterministic_check(user_prompt, state, working_dir)
    if deterministic == CHECK_PASSED:
        return CompletionVerdict(True, "", [], True)
    if deterministic == CHECK_FAILED:
        return CompletionVerdict(False, "deterministic completion check failed", [], True)

    completed = get_list(state, "completed_tasks")
    step_groups = get_list(state, "completed_step_groups")
    # Build evidence: per-task step summaries (action + basename + output snippet, ≤5 per task)
    evidence_lines: list[str] = []
    i = 0
    for task in completed:
        evidence_lines.append(f"Task {i + 1}: {as_str(task)}")
        if i < len(step_groups):
            group = step_groups[i]
            if isinstance(group, list):
                for item in group[:5]:
                    s = as_dict(item)
                    arg = get_str(s, "arg")
                    if "/" in arg:
                        arg = path_name(arg)
                    out = get_str(s, "output")[:80]
                    evidence_lines.append(f"  - {as_str(s['action'])} {arg}: {out}")
        i += 1
    evidence = "\n".join(evidence_lines)
    # File listing
    files: list[str] = []
    try:
        files = sorted(os.listdir(working_dir))[:50]
    except OSError:
        files = []
    user_msg = (
        f"GOAL:\n{user_prompt}\n\n"
        f"COMPLETED TASKS AND EVIDENCE:\n{evidence}\n\n"
        f"FILES IN WORKING DIRECTORY:\n{json.dumps(str_items(files))}"
    )
    messages: list[JSONValue] = [
        _message("system", SYSTEM_VALIDATE),
        _message("user", user_msg),
    ]
    try:
        decoded = client.ask(
            messages,
            max_tokens,
            True,
            "high",
            max_retries,
            timeout,
            get_str(state, "reasoning_policy", DEFAULT_REASONING_POLICY),
            "final_validator",
            "validation",
        )
    except LLMTransportError as transport_error:
        emit(f"  Validation transport error (no verdict): {transport_error}")
        return None
    except ReplyDecodeError as decode_error:
        emit(f"  Validation parse error (no verdict): {decode_error}")
        return None
    except LLMApiError as api_error:
        emit(f"  Validation parse error (no verdict): {api_error}")
        return None
    parsed = parse_validation(decoded.obj)
    if parsed is None:
        emit(f"  Validation returned unexpected format: {decoded.obj}")
        return None
    return CompletionVerdict(parsed.valid, parsed.reason, parsed.missing, parsed.deterministic)


def _compile_repair_action(
    error_output: str, working_dir: str, cmd: str, enabled: bool
) -> dict[str, JSONValue] | None:
    """Propose a normal write action for a known C include diagnostic, or None.

    This function never mutates the workspace. It inspects the unique
    candidate source and, when a known missing-include diagnostic matches,
    returns an ordinary full-file write action — workspace-relative ``arg``,
    repaired ``content``, and the human description in ``reasoning`` — for the
    controller to dispatch through the action executor and record like any
    other step."""
    if not enabled:
        return None
    for include in ("#include <stdio.h>", "#include <string.h>"):
        diagnostic_re = _STDIO_DIAGNOSTIC_RE if "stdio" in include else _STRING_DIAGNOSTIC_RE
        if not diagnostic_re.search(error_output):
            continue
        candidates = [
            f
            for f in _compile_repair_candidates(error_output, cmd, working_dir)
            if _C_SOURCE_RE.search(path_name(f))
        ]
        if len(candidates) != 1:
            return None
        f = candidates[0]
        if os.path.islink(f):
            # The atomic write replaces the named leaf, so a symlinked
            # candidate must be repaired at its referent or the repository's
            # symlink layout would be silently destroyed.
            f = path_resolve(f)
            if not os.path.exists(f):
                return None
        try:
            text = read_text(f)
        except (OSError, UnicodeDecodeError):
            # An unreadable or non-UTF-8 candidate cannot be repaired; the
            # compile error surfaces to the model as a typed failure.
            return None
        if include in text:
            return None
        lines = text.split("\n")
        insert_idx = 0
        j = 0
        for line in lines:
            if line.startswith("#include"):
                insert_idx = j + 1
            j += 1
        lines.insert(insert_idx, include)
        relative = path_relative_to(f, working_dir)
        action: dict[str, JSONValue] = {
            "action": "write",
            "arg": relative if relative is not None else f,
            "content": "\n".join(lines),
            "reasoning": f"Auto-inserted {include}",
        }
        return action
    return None


class RunConfig:
    """Resolved immutable per-run configuration.

    Every outcome-affecting setting — validation mode, the compile-repair
    arm, guard thresholds, capability budgets (on ``llm``), and run limits —
    is one frozen per-run surface whose hash is logged at run_start and
    returned in the config metadata."""

    def __init__(
        self,
        llm: LLMSettings,
        allow_system_installs: bool = False,
        allow_network: bool = True,
        reasoning_policy: str = DEFAULT_REASONING_POLICY,
        max_replans: int = MAX_REPLANS,
        max_tasks: int = MAX_TASKS,
        max_steps: int = MAX_STEPS,
        goal_context_chars: int = GOAL_CONTEXT_CHARS,
        final_validate: str = "auto",
        compile_repair: bool = True,
        step_policy: str = "heuristic",
        write_pressure_observations: int = WRITE_PRESSURE_OBSERVATIONS,
        observe_tail_reserve: int = OBSERVE_TAIL_RESERVE,
        rewrite_pressure_writes: int = REWRITE_PRESSURE_WRITES,
        rewrite_skip_writes: int = REWRITE_SKIP_WRITES,
        max_task_local_replans: int = MAX_TASK_LOCAL_REPLANS,
    ) -> None:
        self.llm = llm
        self.allow_system_installs = allow_system_installs
        self.allow_network = allow_network
        self.reasoning_policy = reasoning_policy
        self.max_replans = max_replans
        self.max_tasks = max_tasks
        self.max_steps = max_steps
        self.goal_context_chars = goal_context_chars
        self.final_validate = final_validate
        self.compile_repair = compile_repair
        self.step_policy = step_policy
        self.write_pressure_observations = write_pressure_observations
        self.observe_tail_reserve = observe_tail_reserve
        self.rewrite_pressure_writes = rewrite_pressure_writes
        self.rewrite_skip_writes = rewrite_skip_writes
        self.max_task_local_replans = max_task_local_replans


class RunController:
    """Thin coordinator over planning, task attempts, step decisions, and
    finalization.

    Run-scoped data lives on :class:`RunState`, attempt-scoped data on
    :class:`TaskAttemptState`; ``done``/``fail`` remain controller concerns,
    and every dispatch — normal, deterministic repair, and retry — flows
    through the one step recorder.
    """

    def __init__(
        self,
        user_prompt: str,
        working_dir: str,
        cfg: RunConfig,
        client: LLMClient,
        host: Host,
        clock: Callable[[], float],
        log: Callable[[str], None],
        event: Callable[[dict[str, JSONValue]], None],
    ) -> None:
        if cfg.reasoning_policy not in REASONING_POLICIES:
            raise ValueError(f"reasoning_policy must be one of {', '.join(REASONING_POLICIES)}")
        self.user_prompt: str = user_prompt
        self.working_dir: str = working_dir
        self.max_replans: int = cfg.max_replans
        self.max_tasks: int = cfg.max_tasks
        self.max_steps: int = cfg.max_steps
        # A zero budget would silently report a plausible failure without
        # doing any work.
        if self.max_replans < 1:
            raise ValueError("max_replans must be a positive integer")
        if self.max_tasks < 1:
            raise ValueError("max_tasks must be a positive integer")
        if self.max_steps < 1:
            raise ValueError("max_steps must be a positive integer")
        self.reasoning_policy: str = cfg.reasoning_policy
        meta = cfg.llm
        if meta.timeout < 1:
            raise ValueError("timeout must be a positive integer")
        if meta.replan_timeout < 1:
            raise ValueError("replan_timeout must be a positive integer")
        if meta.max_retries < 0:
            raise ValueError("max_retries must be a non-negative integer")
        self._llm_meta: LLMSettings = meta
        if cfg.goal_context_chars < 1:
            raise ValueError("goal_context_chars must be a positive integer")
        self.goal_context_chars: int = cfg.goal_context_chars
        # Freeze the executor/replanner view once so all policy arms receive
        # the same task context.
        self.goal_context: str = user_prompt[: cfg.goal_context_chars]
        self._client: LLMClient = client
        self._executor: ActionExecutor = ActionExecutor(working_dir, host)
        self._host: Host = host
        self._clock: Callable[[], float] = clock
        self._log: Callable[[str], None] = log
        self._event_sink: Callable[[dict[str, JSONValue]], None] = event
        self._policy: dict[str, JSONValue] = {
            "allow_system_installs": cfg.allow_system_installs,
            "allow_network": cfg.allow_network,
        }
        # Outcome-affecting settings resolve once here: validation mode, the
        # compile-repair arm, and the guard thresholds are frozen for the run,
        # and the hash below pins what actually ran.
        self.final_validate: str = cfg.final_validate
        self.compile_repair: bool = cfg.compile_repair
        if cfg.step_policy not in STEP_POLICY_NAMES:
            raise ValueError(f"step_policy must be one of {', '.join(STEP_POLICY_NAMES)}")
        self.guards: GuardThresholds = GuardThresholds(
            cfg.write_pressure_observations,
            cfg.observe_tail_reserve,
            cfg.rewrite_pressure_writes,
            cfg.rewrite_skip_writes,
            cfg.max_task_local_replans,
        )
        # Snapshot budgets and the credential-free metadata/hash once per run.
        capabilities = meta.resolved_capability_profile()
        self._planner_tokens: int = capabilities.planner_tokens
        self._step_tokens: int = capabilities.step_tokens
        self._task_replan_tokens: int = capabilities.task_replan_tokens
        self._validation_tokens: int = capabilities.validation_tokens
        timeouts: dict[str, JSONValue] = {
            "planner_initial": meta.timeout,
            "planner_replan": meta.replan_timeout,
            "executor": meta.timeout,
            "task_replan": meta.timeout,
            "final_validation": meta.timeout,
        }
        retries: dict[str, JSONValue] = {
            "planner": meta.max_retries,
            "executor": meta.max_retries,
            # These two deliberately remain single-shot calls.
            "task_replan": 0,
            "final_validation": 0,
        }
        budgets: dict[str, JSONValue] = {
            "step_tokens": capabilities.step_tokens,
            "step_write_tokens": capabilities.step_write_tokens,
            "planner_max_tokens": capabilities.planner_tokens,
            "task_replan_max_tokens": capabilities.task_replan_tokens,
            "final_validation_max_tokens": capabilities.validation_tokens,
            "llm_max_retries": meta.max_retries,
            # OpenRouter reasoning tokens share the HTTP completion allowance;
            # request construction floors max_tokens by the selected effort
            # using this frozen table.
            "reasoning_token_floors": meta.reasoning_token_floor_metadata(),
        }
        limits: dict[str, JSONValue] = {
            "max_replans": self.max_replans,
            "max_tasks": self.max_tasks,
            "max_steps": self.max_steps,
            "goal_context_chars": self.goal_context_chars,
        }
        openrouter = meta.backend == "openrouter"
        self._config_payload: dict[str, JSONValue] = {
            "backend": meta.backend,
            # The endpoint identity and request deadline are outcome-affecting:
            # two local servers or two timeouts must not share a hash. `api`
            # is operator-supplied endpoint configuration; the Authorization
            # credential never rides in it.
            "api": meta.api,
            "model": meta.model,
            "capability_profile": capabilities.describe(),
            "action_transport": ACTION_TRANSPORT,
            "provider": meta.provider if openrouter else "",
            "reasoning_effort": meta.reasoning_effort if openrouter else "",
            "allow_provider_fallbacks": meta.allow_fallbacks,
            "require_provider_parameters": meta.require_parameters,
            "timeout_s": meta.timeout,
            "timeouts_s": timeouts,
            "retry_budgets": retries,
            "llm_provenance": "pinned_config",
            "policy": copy_dict(self._policy),
            "reasoning_policy": self.reasoning_policy,
            "final_validate": self.final_validate,
            "compile_repair": self.compile_repair,
            "step_policy": cfg.step_policy,
            "guards": self.guards.describe(),
            "budgets": budgets,
            "limits": limits,
        }
        self.config_hash: str = _config_hash(self._config_payload)
        self._planned_tasks: list[JSONValue] = []
        self.run_state: RunState = RunState(
            self.reasoning_policy,
            self.goal_context_chars,
            clock,
            event,
            self.guards.rewrite_pressure_writes,
            self.guards.rewrite_skip_writes,
        )
        self.state: dict[str, JSONValue] = self.run_state.data
        self.history: list[JSONValue] = self.run_state.history
        self.recorder: StepRecorder = self.run_state.recorder
        # The policy components are constructed last so they hold run-scoped
        # state over the same run_state/guards the controller sequences: the
        # selected pressure arm, the shared incomplete-write obligations, and
        # the terminal/validation policy.
        services = PolicyServices(
            self.run_state, working_dir, log, self.max_steps, self.guards.observe_tail_reserve
        )
        self.step_policy: StepPolicy = make_step_policy(cfg.step_policy, services)
        self.obligations: WriteObligations = WriteObligations(services)

        def validate() -> CompletionVerdict | None:
            return _validate_completion(
                self.user_prompt,
                self.state,
                self.working_dir,
                self._client,
                self._log,
                self._validation_tokens,
                self._llm_meta.timeout,
                0,
            )

        self.completion: CompletionPolicy = CompletionPolicy(
            CompletionContext(
                self.run_state,
                user_prompt,
                working_dir,
                self.final_validate,
                self.max_replans,
                validate,
                log,
                event,
            )
        )

    def progress(self) -> RunProgress:
        return RunProgress(self.state)

    def _emit(self, msg: str) -> None:
        self._log(msg)

    def _event(self, event: dict[str, JSONValue]) -> None:
        self._event_sink(event)

    def _dispatch(self, action: JSONValue) -> ActionResult:
        """One normalized dispatch through the action seam."""
        return self._executor.dispatch_value(action)

    def config_metadata(self) -> dict[str, JSONValue]:
        """Resolved immutable run configuration for the structured result.

        A fresh projection of the hash-logged payload — the same fields the
        ``run_start`` event carries — plus ``config_hash``. Never includes
        credentials."""
        metadata = as_dict(json.loads(json.dumps(self._config_payload)))
        metadata["config_hash"] = self.config_hash
        return metadata

    def run(self) -> dict[str, JSONValue]:
        """Drive planning, task attempts, validation, and finalization.

        The one typed :class:`RunOutcome` built at the terminal site is
        projected into both the ``run_end`` event and the structured
        result, so the two records cannot disagree."""
        self._log_run_start()
        self._preflight()
        outcome: RunOutcome | None = None
        for replan in range(self.max_replans):
            tasks = self._plan(replan)
            if tasks is None:
                continue  # consumes a plan attempt
            if self._execute_tasks(tasks):
                outcome = self.completion.try_finish(replan)
                if outcome is not None:
                    break
        if outcome is None:
            outcome = self.completion.exhausted()
        self._event(outcome.run_end_event())
        result: dict[str, JSONValue] = {
            "status": outcome.status,
            "state": self.state,
            "log": self.history,
            "outcome": outcome.describe(),
        }
        return result

    def _log_run_start(self) -> None:
        self._emit(f"Prompt: {self.user_prompt}")
        self._emit(f"Working directory: {self.working_dir}")
        # The full resolved configuration and its hash are pinned into the run
        # record before any model call.
        event: dict[str, JSONValue] = {
            "event": "run_start",
            "prompt": self.user_prompt,
            "working_dir": self.working_dir,
        }
        event.update(self.config_metadata())
        self._event(event)

    def _preflight(self) -> None:
        # Preflight: probe environment and set the run's resolved policy
        env = preflight_probe(self.working_dir, self._host)
        self.state["environment"] = env
        self.state["policy"] = copy_dict(self._policy)
        self._emit(f"Environment: platform={as_str(env['platform'])} arch={as_str(env['arch'])}")
        self._emit(f"Available tools: {env['available_tools']}")
        if truthy(env["missing_tools"]):
            self._emit(f"Missing tools: {env['missing_tools']}")
        self._emit(f"Package managers: {env['package_managers']}")
        self._emit(f"Policy: allow_system_installs={self._policy['allow_system_installs']}")

    def _plan(self, replan: int) -> list[str] | None:
        """One planning attempt; returns the task list or None on failure."""
        self._emit("=" * 40)
        t_plan = self._clock()
        self._emit(f"Planning (attempt {replan + 1}/{self.max_replans})...")
        self.state["planning_attempt"] = replan
        transport_error = ""
        failed = False
        plan: JSONValue = None
        try:
            plan = get_plan(
                self.user_prompt,
                self.state,
                self._client,
                self._policy,
                self._planner_tokens,
                self.max_tasks,
                self._llm_meta.timeout,
                self._llm_meta.replan_timeout,
                self._llm_meta.max_retries,
            )
        except LLMTransportError as transport_failure:
            transport_error = str(transport_failure)
            failed = True
        except LLMApiError as api_failure:
            transport_error = str(api_failure)
            failed = True
        except ReplyDecodeError:
            # The client already retried the plan schema; a persistently
            # malformed reply consumes this planning attempt.
            plan = None
        if failed:
            self._emit(f"  Planner transport error: {transport_error}")
            self.progress().add_error(f"[unknown] Planner transport error: {transport_error[:100]}")
            entry: dict[str, JSONValue] = {
                "event": "plan_error",
                "replan": replan,
                "error": transport_error[:200],
            }
            self.history.append(entry)
            logged: dict[str, JSONValue] = {
                "event": "plan_error",
                "replan": replan,
                "error": transport_error[:200],
                "wall_s": round(self._clock() - t_plan, 2),
            }
            self._event(logged)
            return None
        parsed = parse_plan(plan, self.max_tasks)
        if parsed is None:
            error = "[malformed_plan] planner returned no valid tasks"
            self.progress().add_error(error)
            self._emit(f"  Planner contract error: {error}")
            contract: dict[str, JSONValue] = {
                "event": "plan_error",
                "replan": replan,
                "error": error,
            }
            self.history.append(contract)
            contract_logged: dict[str, JSONValue] = {
                "event": "plan_error",
                "replan": replan,
                "error": error,
                "wall_s": round(self._clock() - t_plan, 2),
            }
            self._event(contract_logged)
            return None
        tasks = list(parsed.tasks)
        self.state["errors"] = json_list()  # reset errors each replan; planner already saw them
        plan_wall = self._clock() - t_plan
        self._emit(f"Plan ({plan_wall:.1f}s, planner_wall_time={plan_wall:.1f}s): {tasks}")
        # The history entry shares the live task list: a task-local
        # replacement is visible there, as in the run's returned log.
        self._planned_tasks = str_items(tasks)
        planned: dict[str, JSONValue] = {
            "event": "plan",
            "replan": replan,
            "tasks": self._planned_tasks,
        }
        self.history.append(planned)
        planned_logged: dict[str, JSONValue] = {
            "event": "plan",
            "replan": replan,
            "tasks": str_items(tasks),
            "wall_s": round(plan_wall, 2),
        }
        self._event(planned_logged)
        return tasks

    def _execute_tasks(self, tasks: list[str]) -> bool:
        """Run the plan's tasks in order; True when every task completed."""
        all_done = True
        i = 0
        while i < len(tasks):
            progress = self.progress()
            # Carry over last step from previous task so executor has cross-task context
            prev_last: list[JSONValue] = []
            carried = progress.optional_last_steps()
            if carried:
                prev_last.append(carried[-1])
            t_task = self._clock()
            # Scope for no_write_executed: an earlier task's write must not
            # mask a stall in this one.
            self.state["task_start_step_count"] = len(progress.all_steps())
            attempt = self._run_task(i, tasks, prev_last)
            task = tasks[i]
            task_done = attempt.done
            if task_done:
                blocker = self.obligations.completion_blocker()
                if blocker is not None:
                    progress.add_error(
                        f"[incomplete_write] {blocker.name} at "
                        f"{blocker.recovery_arg}: completion refused"
                    )
                    self._emit(f"  Task completion refused: {blocker.name} is incomplete")
                    task_done = False
            if task_done:
                progress.completed_tasks().append(task)
                progress.completed_step_groups().append(attempt.steps)
                self._emit(f"  Task complete. ({self._clock() - t_task:.1f}s)")
                completed: dict[str, JSONValue] = {
                    "event": "task_complete",
                    "task_index": i,
                    "task": task,
                    "wall_s": round(self._clock() - t_task, 2),
                }
                self._event(completed)
            else:
                all_done = False
                self._emit(f"  Task failed, will replan. ({self._clock() - t_task:.1f}s)")
                failed: dict[str, JSONValue] = {
                    "event": "task_failed",
                    "task_index": i,
                    "task": task,
                    "wall_s": round(self._clock() - t_task, 2),
                }
                self._event(failed)
                break
            i += 1
        return all_done

    def _new_attempt(self, task: str) -> TaskAttemptState:
        """Fresh attempt state for one task under the run's guard thresholds."""
        return TaskAttemptState(
            task, _is_write_shaped(task), self.guards.write_pressure_observations
        )

    def _run_task(self, i: int, tasks: list[str], prev_last: list[JSONValue]) -> TaskAttemptState:
        """Attempt one task with the run's task-local replan budget.

        A task-local replacement is stored back into ``tasks[i]`` so the run
        record carries the text that was actually attempted.
        """
        task = tasks[i]
        # Inner retry loop — try task-local replan before full replan
        attempt = self._new_attempt(task)
        saved_errors: list[JSONValue] = []
        for task_attempt in range(1 + self.guards.max_task_local_replans):
            self.state["current_task"] = task
            self.state["task_index"] = f"{i + 1}/{len(tasks)}"
            carried: list[JSONValue] = []
            for item in prev_last:
                carried.append(item)
            self.state["last_steps"] = carried
            self._emit(f"--- Task {i + 1}/{len(tasks)}: {task} ---")

            # Reset per-attempt execution state (the task may be a replacement)
            attempt = self._new_attempt(task)
            completed_repair = _task_satisfied_by_deterministic_repair(task, self.state)
            if (
                completed_repair is not None
                and not self.step_policy.allows_deterministic_completion()
            ):
                # An automatic completion must pass the same policy gate as a
                # model done: with an open verification obligation the attempt
                # runs normally so the model can verify first.
                completed_repair = None
            if completed_repair is not None:
                self._emit(
                    "  auto-done (deterministic repair already satisfied task: "
                    f"{get_str(completed_repair, 'output')[:60]})"
                )
                attempt.steps.append(completed_repair)
                attempt.done = True
                break
            self._run_attempt(i, attempt)

            if attempt.done:
                break  # break task_attempt loop — success

            progress = self.progress()
            # Try task-local replan before falling through to full replan
            if task_attempt < self.guards.max_task_local_replans:
                saved_errors = []
                for error in progress.errors():
                    saved_errors.append(error)
                t_lr = self._clock()
                replan = replan_task(
                    task,
                    progress.errors(),
                    progress.completed_tasks(),
                    self.state,
                    self.goal_context,
                    self._client,
                    self._policy,
                    self.goal_context_chars,
                    self._task_replan_tokens,
                    self._llm_meta.timeout,
                    0,
                )
                replacement = replan.task
                lr_wall = self._clock() - t_lr
                if replacement:
                    self._emit(f"  Task-local replan ({lr_wall:.1f}s): '{replacement[:60]}'")
                    accepted: dict[str, JSONValue] = {
                        "event": "task_local_replan",
                        "task_index": i,
                        "original": task[:120],
                        "replacement": replacement[:120],
                        "ok": True,
                        "llm_wall_s": round(lr_wall, 2),
                    }
                    self._event(accepted)
                    task = replacement
                    tasks[i] = replacement
                    self._planned_tasks[i] = replacement
                    self.state["errors"] = json_list()
                    continue  # retry with replacement
                else:
                    reject_reason = replan.reject_reason if replan.reject_reason else "unknown"
                    self._emit(f"  Task-local replan failed ({lr_wall:.1f}s), will full replan.")
                    rejected: dict[str, JSONValue] = {
                        "event": "task_local_replan",
                        "task_index": i,
                        "original": task[:120],
                        "replacement": None,
                        "ok": False,
                        "llm_wall_s": round(lr_wall, 2),
                        "reject_reason": reject_reason,
                    }
                    self._event(rejected)
                    self.state["errors"] = saved_errors
            else:
                # Replacement attempt also failed — merge original errors back
                # so full replan sees both failure contexts
                merged: list[JSONValue] = []
                for error in saved_errors:
                    merged.append(error)
                for error in progress.errors():
                    merged.append(error)
                self.state["errors"] = merged
            # Fall through — task failed, no more local attempts
            break
        return attempt

    def _run_attempt(self, i: int, attempt: TaskAttemptState) -> None:
        """One executor pass over the step budget; sets ``attempt.done``."""
        for step in range(self.max_steps):
            ctx = self._select_action(i, attempt, step)
            if ctx is None:
                return
            flow = self._decide_step(ctx, attempt)
            if flow == FLOW_DISPATCH:
                flow = self._execute_step(ctx, attempt)
            if flow == FLOW_END_ATTEMPT:
                return

    def _select_action(self, i: int, attempt: TaskAttemptState, step: int) -> StepContext | None:
        """Ask the executor for one action; None ends the attempt."""
        t_step = self._clock()
        user_msg = build_step_message(
            attempt.task,
            self.state,
            self._policy,
            self.goal_context,
            step,
            self.max_steps,
            self.goal_context_chars,
            self.step_policy.write_pressure(attempt),
            self.step_policy.validate_pressure(attempt),
        )
        messages: list[JSONValue] = [
            _message("system", SYSTEM_STEP),
            _message("user", user_msg),
        ]
        try:
            decoded = self._client.ask(
                messages,
                self._step_tokens,
                attempt.use_think,
                "",
                self._llm_meta.max_retries,
                self._llm_meta.timeout,
                self.reasoning_policy,
                attempt.reasoning_trigger,
                "action",
            )
        except LLMTransportError as transport_error:
            self._emit(
                f"  [{step + 1}] LLM transport error ({self._clock() - t_step:.1f}s): {transport_error}"
            )
            self.progress().add_error(
                f"[unknown] LLM transport error on task '{attempt.task}': {str(transport_error)[:100]}"
            )
            return None
        except ReplyDecodeError as decode_error:
            # Typed parse failures: the replanner should know whether the
            # action envelope was truncated at the token budget, of the wrong
            # response type, or simply malformed.
            if decode_error.envelope_error:
                etype = decode_error.envelope_error
            elif decode_error.response_truncated:
                etype = "response_truncated"
            elif decode_error.malformed_action:
                etype = "malformed_action"
            else:
                etype = "unknown"
            self._parse_failure(i, attempt, step, t_step, etype, str(decode_error))
            return None
        except LLMApiError as api_error:
            self._parse_failure(i, attempt, step, t_step, "unknown", str(api_error))
            return None
        selected = decoded.action
        if selected is None:
            self._parse_failure(i, attempt, step, t_step, "malformed_action", "no action decoded")
            return None
        action = selected.envelope
        act = action.name
        self.recorder.selected()
        self._emit(f"  [{step + 1}] {act}: {action.text('arg')[:80]}")
        return StepContext(i, step, t_step, action, act, selected.transport)

    def _parse_failure(
        self, i: int, attempt: TaskAttemptState, step: int, t_step: float, etype: str, text: str
    ) -> None:
        self._emit(f"  [{step + 1}] LLM parse error ({self._clock() - t_step:.1f}s) [{etype}]")
        self.progress().add_error(
            f"[{etype}] LLM parse error on task '{attempt.task}': {text[:100]}"
        )
        event: dict[str, JSONValue] = {
            "event": "step_error",
            "task_index": i,
            "step": step,
            "error_type": etype,
        }
        self._event(event)

    def _decide_step(self, ctx: StepContext, attempt: TaskAttemptState) -> int:
        """Sequence the shared invariants and the policy arm.

        Order: write-truncation/obligation preparation and the completion
        blocker are shared invariants; the policy arm's discipline runs
        next; duplicate/stuck loop protection guards every arm last. The
        individual algorithms live on the components, not here.
        """
        if ctx.act == "done":
            return self._handle_done(ctx, attempt)
        if ctx.act == "fail":
            reason = ctx.action.text("reasoning", "no reason")
            self._emit(f"  FAIL ({self._clock() - ctx.started:.1f}s): {reason}")
            self.progress().add_error(f"Task '{attempt.task}': {reason}")
            self.recorder.control(ctx.task_index, ctx.step, ctx.act)
            return FLOW_END_ATTEMPT
        flow = self.obligations.prepare(ctx)
        if flow == FLOW_DISPATCH:
            flow = self.step_policy.guard_action(ctx, attempt)
        if flow == FLOW_DISPATCH:
            flow = self.step_policy.guard_duplicate(ctx, attempt)
        return flow

    def _handle_done(self, ctx: StepContext, attempt: TaskAttemptState) -> int:
        """Accept ``done`` only past the shared blocker and the policy arm."""
        flow = self.obligations.refuse_done(ctx)
        if flow == FLOW_DISPATCH:
            flow = self.step_policy.guard_done(ctx, attempt)
        if flow != FLOW_DISPATCH:
            return flow
        attempt.done = True
        self.recorder.control(ctx.task_index, ctx.step, ctx.act)
        return FLOW_END_ATTEMPT

    def _execute_step(self, ctx: StepContext, attempt: TaskAttemptState) -> int:
        """Dispatch through the action seam and record the receipt."""
        action = ctx.action
        act = ctx.act
        attempt.dup_skip_count = 0  # reset on any non-skipped action
        self.recorder.executed()
        if act in OBSERVE_ACTIONS:
            attempt.observe_executed += 1
        result = self._executor.dispatch(action)
        if result.ok and act == "write":
            self.obligations.note_successful_write(ctx, action)
        if act not in OBSERVE_ACTIONS and result.ok:
            # Counted only on success: a failed mutation must not disarm
            # write pressure or the observation tail reserve.
            attempt.commit_executed += 1
        self.step_policy.note_result(ctx, attempt, result)
        if ctx.truncated_write and result.ok:
            self.obligations.append_resume_anchor(ctx, action, result)
        ok_str = "OK" if result.ok else "FAIL"
        self._emit(f"  -> {ok_str} ({self._clock() - ctx.started:.1f}s): {result.output[:80]}")

        step_entry = self.recorder.record(
            receipt_executed(action, result, self.working_dir, ctx.truncated_write),
            ctx.task_index,
            ctx.step,
            round(self._clock() - ctx.started, 2),
        )

        if not result.ok:
            flow = self._recover_failed_step(ctx, attempt, result)
            if flow == FLOW_DISPATCH:
                # The typed failure is task evidence: a task the model
                # completes after observing a failure must carry that
                # observation into completed_step_groups so the final
                # validator sees what the task actually observed.
                attempt.steps.append(step_entry)
            return flow
        attempt.use_think = False
        attempt.reasoning_trigger = "executor"
        attempt.steps.append(step_entry)
        return FLOW_DISPATCH

    def _recover_failed_step(
        self, ctx: StepContext, attempt: TaskAttemptState, result: ActionResult
    ) -> int:
        """Deterministic repair or typed error; a failure never completes.

        A failing command is typed evidence for the model and the replanner,
        and only an explicit ``done`` can claim the task.
        """
        action = ctx.action
        act = ctx.act
        arg = action.text("arg")
        etype = result.error_type if result.error_type else "unknown"
        if act == "shell" and etype == "compile_error":
            repair_action = _compile_repair_action(
                result.output, self.working_dir, arg, self.compile_repair
            )
            if repair_action is not None:
                # The repair rule only proposes an action; the mutation
                # happens through the ordinary action seam and the one
                # recorder, exactly like a model-selected step.
                repair_result = self._dispatch(repair_action)
                repair_arg = get_str(repair_action, "arg")
                if repair_result.ok:
                    # The policy arm observes the deterministic mutation like
                    # any targeted fix (heuristic: rewrite streak broken;
                    # lifecycle: the repaired target needs verification).
                    repaired: dict[str, JSONValue] = {"arg": repair_arg}
                    self.step_policy.note_deterministic_repair(
                        _mutation_target_key(repaired, self.working_dir)
                    )
                    self._emit(
                        f"  Deterministic repair: {get_str(repair_action, 'reasoning')} "
                        f"in {path_name(repair_arg)}"
                    )
                    attempt.steps.append(
                        self.recorder.record(
                            receipt_deterministic_repair(repair_action, repair_result),
                            ctx.task_index,
                            ctx.step,
                        )
                    )

                    retry_result = self._executor.dispatch(action)
                    self.step_policy.note_deterministic_retry(retry_result)
                    retry_entry = self.recorder.record(
                        receipt_deterministic_retry(action, retry_result),
                        ctx.task_index,
                        ctx.step,
                        round(self._clock() - ctx.started, 2),
                    )
                    if retry_result.ok:
                        self._emit(f"  -> OK deterministic retry: {retry_result.output[:80]}")
                        attempt.steps.append(retry_entry)
                        attempt.use_think = False
                        attempt.reasoning_trigger = "executor"
                        return FLOW_NEXT_STEP
                    self._emit(f"  -> FAIL deterministic retry: {retry_result.output[:80]}")
                    result = retry_result
                    etype = result.error_type if result.error_type else "unknown"
                else:
                    # A refused repair dispatch mutated nothing, but the
                    # attempt itself is recorded with its real failed result
                    # so history/JSONL show the dispatch; the original typed
                    # compile error stands for recovery.
                    self._emit(f"  Deterministic repair failed: {repair_result.output[:80]}")
                    self.recorder.record(
                        receipt_deterministic_repair(repair_action, repair_result),
                        ctx.task_index,
                        ctx.step,
                    )

        err_output = result.output[:100]
        hint = _RECOVERY_HINTS.get(etype)
        if hint:
            err_output = f"{err_output} → {hint}"
            self.recorder.append_recovery_hint(hint)
        self.progress().add_error(f"[{etype}] {act} {arg[:60]}: {err_output}")
        attempt.use_think = etype not in _NO_THINK_ERRORS
        attempt.reasoning_trigger = f"execution_error:{etype}"
        return FLOW_DISPATCH
