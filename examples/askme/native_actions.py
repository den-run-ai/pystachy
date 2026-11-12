"""Action layer of the native AskMe port (mirrors ``actions.py``).

One registry names every action, its category and its fields.
``parse_action_envelope`` is the single semantic contract for reply decode,
controller intake and dispatch; ``ActionExecutor`` holds the six handlers.
``done`` and ``fail`` stay controller decisions and are never dispatched.

This layer is not a sandbox: handlers run with the launching user's host
permissions, and workspace-relative paths organize files without confining
shell commands, absolute paths, or traversal.
"""

from __future__ import annotations

import bisect
import os
import re
import shlex
from typing import Callable

from native_host import (
    Host,
    append_text,
    byte_length,
    list_dir,
    path_is_absolute,
    path_join,
    path_name,
    path_parent,
    path_relative_to,
    path_resolve,
    path_str,
    read_bytes,
    read_text,
    read_text_replace,
    sha256_hex,
    write_text,
)
from native_json import (
    JSONValue,
    dumps_pretty,
    get_flag,
    get_int,
    get_str,
    json_copy,
    str_items,
    truthy,
)

MAX_RESULT = 300  # chars kept from command output

READ_LINES = 60  # max lines per read window
READ_CHARS = 1200  # max Unicode code points per read page
READ_LIMIT_MAX = 200  # hard cap on model-specified read limit
SEARCH_MAX_MATCHES = 15  # bounded literal search results
SEARCH_MAX_CHARS = 1500  # bounded search output
SEARCH_MAX_FILES = 500  # bounded search scan
TREE_MAX_ENTRIES = 60  # bounded repository-tree listing
TREE_MAX_CHARS = 1500  # bounded tree output
TREE_MAX_DEPTH = 3  # bounded tree walk depth
OBSERVE_STATE_CHARS = 1500  # executor-state budget for observation step output

# Command patterns that need longer timeouts
_LONG_TIMEOUT_PATTERNS = [
    "install",
    "update",
    "upgrade",  # package managers
    "cmake",
    "make",
    "cargo build",
    "go build",  # build tools
    "npm install",
    "pip install",
    "brew ",  # specific installers
]
SHELL_TIMEOUT = 30  # default
SHELL_TIMEOUT_LONG = 120  # for install/build commands
SHELL_TIMEOUT_MAX = 300  # hard cap for model-specified timeout

# Model-controlled read positions are bounded so the wire contract is finite
# and deterministic; the cap is far larger than a workspace needs.
READ_POSITION_MAX = 2_147_483_647


def _get_shell_timeout(cmd: str, hint: int | None = None) -> int:
    """Return timeout for a shell command. Uses longer timeout for install/build patterns."""
    if hint is not None:
        return min(max(hint, 5), SHELL_TIMEOUT_MAX)
    cmd_lower = cmd.lower()
    for pattern in _LONG_TIMEOUT_PATTERNS:
        if pattern in cmd_lower:
            return SHELL_TIMEOUT_LONG
    return SHELL_TIMEOUT


# VCS / dependency / build directories excluded from search and tree walks.
_REPO_SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "target",
        "dist",
        "build",
    }
)


def _step_path(arg: str, working_dir: str) -> str:
    if path_is_absolute(arg):
        return path_str(arg)
    return path_join(working_dir, arg)


def _mutation_target_key(step: dict[str, JSONValue], working_dir: str | None = None) -> str | None:
    """Stable operation-aware identity for write/edit transition tracking."""
    target = step.get("_target")
    if isinstance(target, str) and target.strip():
        return target
    arg = step.get("arg")
    if not (isinstance(arg, str) and arg.strip()):
        return None
    if working_dir is not None:
        path = _step_path(arg, working_dir)
        if "\x00" in path:
            # realpath cannot name this file; keep the lexical identity.
            return os.path.normpath(os.path.abspath(path))
        if get_flag(step, "append") or get_flag(step, "_append"):
            # Append opens the target directly and follows a leaf symlink.
            path = path_resolve(path)
        else:
            # Atomic overwrite/edit replaces a leaf symlink rather than
            # mutating its referent. Resolve directory aliases only.
            path = path_join(path_resolve(path_parent(path)), path_name(path))
        return os.path.normpath(path)
    return os.path.normpath(arg)


def _target_recovery_arg(target: str | None, working_dir: str) -> str | None:
    """Action-ready spelling for a frozen mutation target."""
    if target is None or not target.strip():
        return None
    # Keep the canonical absolute identity. A relative spelling can silently
    # retarget if the working-directory path (or one of its parents) is itself
    # a symlink changed by a shell step during recovery.
    return target


_COMPILER_EXES = frozenset(
    {
        "cc",
        "gcc",
        "g++",
        "clang",
        "clang++",
        "c++",
        "rustc",
        "javac",
        "make",
        "cmake",
        "cargo",
        "go",
        "tsc",
        "swiftc",
    }
)

_COMPILE_DIAGNOSTIC_RE = re.compile(
    r"error generated|implicit function declaration|undeclared (?:library )?function|"
    r"include the header <[^>]+>|undefined reference|undefined symbols"
)


def _is_compiler_command(cmd: str) -> bool:
    """Check if a shell command invokes a compiler or build tool."""
    try:
        parts = shlex.split(cmd)
    except ValueError:
        parts = cmd.split()
    if not parts:
        return False
    exe = os.path.basename(parts[0])
    return exe in _COMPILER_EXES


def classify_error(output: str, action: str = "shell", cmd: str = "") -> str:
    """Classify an error output into a typed category for structured diagnostics."""
    out = output.lower()
    if "timeout" in out or output == "TIMEOUT":
        return "timeout"
    if "command not found" in out:
        return "missing_tool"
    if "permission denied" in out:
        return "permission_denied"
    if "no such file" in out or "no such file or directory" in out:
        if action == "shell" and cmd and _is_compiler_command(cmd):
            return "compile_error"
        return "missing_file"
    if action == "shell" and cmd and _is_compiler_command(cmd):
        if _COMPILE_DIAGNOSTIC_RE.search(out):
            return "compile_error"
    if "syntax error" in out or "error:" in out:
        return "compile_error"
    return "unknown"


def _read_key(action: dict[str, JSONValue]) -> list[JSONValue]:
    """Identity for duplicate-read detection, including every range field."""
    arg = action.get("arg", "")
    cursor = action.get("cursor")
    if cursor is not None:
        # A cursor continuation always carries its limit (parser contract).
        limit = action["limit"]
        sha = action.get("sha256")
        cursor_key: list[JSONValue] = [arg, "cursor", cursor, limit, sha if truthy(sha) else ""]
        return cursor_key
    line_key: list[JSONValue] = [
        arg,
        "lines",
        action.get("offset", 1),
        action.get("limit", READ_LINES),
    ]
    return line_key


class ActionProtocolError:
    """A precise, non-throwing rejection at the model-action boundary."""

    def __init__(self, error_type: str, message: str, field: str | None = None) -> None:
        self.error_type = error_type
        self.message = message
        self.field = field


class ActionSpec:
    """One action's registry entry.

    ``allowed`` and ``requires`` feed :func:`parse_action_envelope`. Control
    actions have no handler: the run controller resolves them before dispatch.
    """

    def __init__(self, name: str, category: str, requires: list[str], allowed: list[str]) -> None:
        self.name = name
        self.category = category  # "observe" | "mutate" | "control"
        self.requires = requires
        self.allowed = allowed


# One source of truth for action names, categories and allowed/required
# fields. Registry order is the tool order sent to the model.
ACTION_ORDER = [
    ActionSpec("shell", "mutate", ["arg"], ["action", "arg", "timeout", "reasoning"]),
    ActionSpec(
        "write", "mutate", ["arg", "content"], ["action", "arg", "content", "append", "reasoning"]
    ),
    ActionSpec(
        "edit",
        "mutate",
        ["arg", "find", "replace"],
        ["action", "arg", "find", "replace", "reasoning"],
    ),
    ActionSpec(
        "read",
        "observe",
        ["arg"],
        ["action", "arg", "offset", "limit", "cursor", "sha256", "reasoning"],
    ),
    ActionSpec("search", "observe", ["arg"], ["action", "arg", "path", "reasoning"]),
    ActionSpec("tree", "observe", [], ["action", "arg", "reasoning"]),
    ActionSpec("done", "control", [], ["action", "arg", "reasoning"]),
    ActionSpec("fail", "control", [], ["action", "arg", "reasoning"]),
]
ACTION_SPECS: dict[str, ActionSpec] = {spec.name: spec for spec in ACTION_ORDER}

OBSERVE_ACTIONS = frozenset({"read", "search", "tree"})

_RESERVED_ACTION_FIELDS = frozenset(
    {
        "content_truncated",
        "finish_reason",
        "transport",
        "truncated_write",
    }
)

_STRING_FIELDS = ("arg", "find", "replace", "path", "sha256", "reasoning")
_OPTIONAL_ARG_ACTIONS = ("tree", "done", "fail")


class ActionEnvelope:
    """Immutable normalized model action.

    Values are copied while parsing and the fields are never mutated.
    ``to_dict`` is the detached projection for history and JSON records;
    controller transformations build a new parsed envelope with
    :meth:`with_update` instead of changing the selected action in place.
    """

    def __init__(self, fields: dict[str, JSONValue]) -> None:
        self.fields = fields
        self.name = get_str(fields, "action")

    def has(self, key: str) -> bool:
        return key in self.fields

    def text(self, key: str, default: str = "") -> str:
        """``action.get(key, default)`` for a string field."""
        return get_str(self.fields, key, default)

    def flag(self, key: str) -> bool:
        return get_flag(self.fields, key)

    def to_dict(self) -> dict[str, JSONValue]:
        projected: dict[str, JSONValue] = {}
        for key, value in self.fields.items():
            projected[key] = json_copy(value)
        return projected

    def with_update(self, key: str, value: JSONValue) -> ActionEnvelope:
        candidate = self.to_dict()
        candidate[key] = value
        parsed = parse_action_envelope(candidate)
        if parsed.envelope is None:
            raise ValueError(parsed.message())
        return parsed.envelope


class ParsedAction:
    """Outcome of :func:`parse_action_envelope`: an envelope or a typed error."""

    def __init__(self, envelope: ActionEnvelope | None, error: ActionProtocolError | None) -> None:
        self.envelope = envelope
        self.error = error

    def message(self) -> str:
        return self.error.message if self.error is not None else ""

    def error_type(self) -> str:
        return self.error.error_type if self.error is not None else ""

    def field(self) -> str | None:
        return self.error.field if self.error is not None else None


class ActionTransport:
    """Provider/decoder facts that a model action cannot set."""

    def __init__(self, content_truncated: bool = False) -> None:
        self.content_truncated = content_truncated


class DecodedAction:
    """A normalized action plus transport metadata."""

    def __init__(self, envelope: ActionEnvelope, transport: ActionTransport) -> None:
        self.envelope = envelope
        self.transport = transport


def _action_error(
    message: str, field: str | None = None, error_type: str = "malformed_action"
) -> ParsedAction:
    return ParsedAction(None, ActionProtocolError(error_type, message, field))


def _int_field_error(
    raw: dict[str, JSONValue], field: str, minimum: int, maximum: int
) -> ParsedAction | None:
    value = raw[field]
    if isinstance(value, bool) or not isinstance(value, int):
        return _action_error(f"field '{field}' must be an integer", field)
    if not minimum <= value <= maximum:
        return _action_error(f"field '{field}' must be between {minimum} and {maximum}", field)
    return None


def parse_action_envelope(obj: JSONValue) -> ParsedAction:
    """Parse one model action without mutation or side effects.

    This is the executable action contract for reply decode, controller
    intake, and defensive dispatch. It owns allowed names, field types and
    ranges, reserved metadata, and cross-field continuation rules. Every
    malformed value returns a typed error; it never raises.
    """
    if not isinstance(obj, dict):
        return _action_error("action envelope must be an object")

    raw: dict[str, JSONValue] = {}
    for key, value in obj.items():
        raw[key] = json_copy(value)
    action_name = raw.get("action")
    if not isinstance(action_name, str) or not action_name.strip():
        return _action_error("field 'action' must be a known non-empty string", "action")
    spec = ACTION_SPECS.get(action_name)
    if spec is None:
        return _action_error(f"unknown action: {action_name}", "action", "unknown_action")

    # Deliberate legacy normalization: optional JSON null means the field was
    # omitted for free-form reasoning and for the optional arg on tree/control
    # actions. Required command/path/search args remain strictly typed.
    if "reasoning" in raw and raw["reasoning"] is None:
        raw.pop("reasoning")
    if action_name in _OPTIONAL_ARG_ACTIONS and "arg" in raw and raw["arg"] is None:
        raw.pop("arg")

    reserved = sorted([key for key in raw if key.startswith("_") or key in _RESERVED_ACTION_FIELDS])
    if reserved:
        field = reserved[0]
        return _action_error(f"field '{field}' is reserved for controller metadata", field)
    extras = sorted([key for key in raw if key not in spec.allowed])
    if extras:
        field = extras[0]
        return _action_error(f"field '{field}' is not allowed for action '{action_name}'", field)
    for field in spec.requires:
        if field not in raw:
            return _action_error(f"action '{action_name}' requires field '{field}'", field)

    for field in _STRING_FIELDS:
        if field not in raw:
            continue
        optional_arg = field == "arg" and action_name in _OPTIONAL_ARG_ACTIONS
        nonempty = field not in ("replace", "reasoning") and not optional_arg
        value = raw[field]
        if not isinstance(value, str):
            return _action_error(f"field '{field}' must be a string", field)
        if nonempty and not value.strip():
            return _action_error(f"field '{field}' must be a non-empty string", field)

    if action_name == "write":
        content = raw["content"]
        if not (isinstance(content, str) or isinstance(content, dict) or isinstance(content, list)):
            return _action_error("field 'content' must be a string, object, or list", "content")
        if "append" in raw and not isinstance(raw["append"], bool):
            return _action_error("field 'append' must be a boolean", "append")
    if "timeout" in raw:
        error = _int_field_error(raw, "timeout", 5, SHELL_TIMEOUT_MAX)
        if error is not None:
            return error
    if "offset" in raw:
        error = _int_field_error(raw, "offset", 1, READ_POSITION_MAX)
        if error is not None:
            return error
    if "limit" in raw:
        error = _int_field_error(raw, "limit", 1, READ_LIMIT_MAX)
        if error is not None:
            return error
    if "cursor" in raw:
        error = _int_field_error(raw, "cursor", 0, READ_POSITION_MAX)
        if error is not None:
            return error

    if action_name == "read":
        if "cursor" in raw:
            for field in ("limit", "sha256"):
                if field not in raw:
                    return _action_error(f"read cursor requires field '{field}'", field)
        elif "sha256" in raw:
            return _action_error("field 'sha256' requires a read cursor", "sha256")

    # Registry order gives stable projections regardless of the model's
    # object-key order. Values were copied above, so the envelope does not
    # alias the raw response object.
    normalized: dict[str, JSONValue] = {}
    for field in spec.allowed:
        if field in raw:
            normalized[field] = raw[field]
    return ParsedAction(ActionEnvelope(normalized), None)


class ActionResult:
    """Normalized result of one dispatched action.

    ``ok``/``output``/``error_type`` are the controller-facing core. Every
    action-specific field — truncation flags and reasons, read content and
    continuation cursors, source metadata — travels in ``details``.
    """

    def __init__(
        self,
        ok: bool,
        output: str,
        error_type: str | None = None,
        details: dict[str, JSONValue] | None = None,
    ) -> None:
        self.ok = ok
        self.output = output
        self.error_type = error_type
        self.details: dict[str, JSONValue] = {} if details is None else details

    def get(self, key: str) -> JSONValue:
        """Dict-style access covering core fields and details."""
        if key == "ok":
            return self.ok
        if key == "output":
            return self.output
        if key == "error_type":
            return self.error_type
        return self.details.get(key)

    def to_dict(self) -> dict[str, JSONValue]:
        raw: dict[str, JSONValue] = {"ok": self.ok, "output": self.output}
        if self.error_type is not None:
            raw["error_type"] = self.error_type
        raw.update(self.details)
        return raw


def _pack_observation_lines(
    make_header: Callable[[list[str]], str], records: list[str], reasons: list[str], max_chars: int
) -> tuple[str, list[str]]:
    """Pack complete discovery records, including the header, within a cap."""
    header = make_header(reasons)
    kept: list[str] = []
    used = len(header)
    for record in records:
        extra = 1 + len(record)
        if used + extra > max_chars:
            break
        kept.append(record)
        used += extra
    if len(kept) == len(records):
        return header + ("\n" + "\n".join(kept) if kept else ""), reasons
    final_reasons = reasons + ["chars"]
    header = make_header(final_reasons)
    kept = []
    used = len(header)
    for record in records:
        extra = 1 + len(record)
        if used + extra > max_chars:
            break
        kept.append(record)
        used += extra
    return header + ("\n" + "\n".join(kept) if kept else ""), final_reasons


def _iter_repo_files(root: str, max_files: int, errors: list[str]) -> list[str]:
    """Visible repo files under root, bounded and deterministic (``os.walk`` order)."""
    found: list[str] = []
    stack = [root]
    while stack:
        top = stack.pop()
        dirs, files, readable = list_dir(top)
        if not readable:
            errors.append(top)
            continue
        dirnames = sorted([d for d in dirs if d not in _REPO_SKIP_DIRS and not d.startswith(".")])
        for name in sorted(files):
            if name.startswith("."):
                continue
            found.append(path_join(top, name))
            if len(found) >= max_files:
                return found
        index = len(dirnames) - 1
        while index >= 0:
            child = os.path.join(top, dirnames[index])
            if not os.path.islink(child):
                stack.append(child)
            index -= 1
    return found


def _empty_name_error(path: str) -> ValueError:
    return ValueError("PosixPath(" + repr(path) + ") has an empty name")


class ActionExecutor:
    """Filesystem/shell action handlers behind one dispatch seam.

    Workspace path resolution, exception-to-result shaping, atomic writes, and
    bounded observation packing are shared here instead of being copied per
    action branch. ``done``/``fail`` never execute: they are controller
    decisions, and dispatching one is a typed error.
    """

    def __init__(self, working_dir: str, host: Host) -> None:
        self.working_dir = working_dir
        self.host = host

    def dispatch_value(self, action: JSONValue) -> ActionResult:
        """Parse, then dispatch; a rejected action is a typed result."""
        parsed = parse_action_envelope(action)
        envelope = parsed.envelope
        if envelope is None:
            error_type = parsed.error_type()
            attempted = action.get("action") if isinstance(action, dict) else None
            field = parsed.field()
            if attempted == "read":
                if field == "cursor":
                    error_type = "invalid_read_cursor"
                elif field == "limit":
                    error_type = "invalid_read_limit"
                elif field == "offset":
                    error_type = "invalid_read_offset"
                elif field == "sha256":
                    error_type = "read_cursor_hash_required"
            elif attempted == "shell" and field == "timeout":
                error_type = "invalid_timeout"
            return ActionResult(False, parsed.message(), error_type)
        return self.dispatch(envelope)

    def dispatch(self, action: ActionEnvelope) -> ActionResult:
        act = action.name
        if act == "shell":
            return self._shell(action)
        if act == "write":
            return self._write(action)
        if act == "edit":
            return self._edit(action)
        if act == "read":
            return self._read(action)
        if act == "search":
            return self._search(action)
        if act == "tree":
            return self._tree(action)
        return ActionResult(
            False,
            f"control action '{act}' is resolved by the run controller",
            "control_action",
        )

    def _resolve(self, arg: str) -> str:
        """Resolve a model-supplied path against the working directory."""
        return _step_path(arg, self.working_dir)

    def _exception_result(self, error: Exception, act: str) -> ActionResult:
        out = str(error)[:MAX_RESULT]
        return ActionResult(False, out, classify_error(out, act))

    def _atomic_write_text(self, path: str, content: str) -> None:
        """Write via temp file + rename so a crashed/interrupted write never
        leaves a partial file behind."""
        name = path_name(path)
        if not name:
            raise _empty_name_error(path)
        tmp = path_join(path_parent(path), f"{name}.tmp{os.getpid()}")
        write_text(tmp, content)
        os.replace(tmp, path)

    def _shell(self, action: ActionEnvelope) -> ActionResult:
        command = action.text("arg")
        hint = action.fields.get("timeout")
        timeout = _get_shell_timeout(
            command, hint if isinstance(hint, int) and not isinstance(hint, bool) else None
        )
        try:
            r = self.host.run_shell(command, timeout, self.working_dir)
        except ValueError as e:
            return self._exception_result(e, "shell")
        if r.timed_out:
            return ActionResult(False, "TIMEOUT", "timeout")
        stdout = r.stdout.replace("\r\n", "\n").replace("\r", "\n")
        stderr = r.stderr.replace("\r\n", "\n").replace("\r", "\n")
        tail_start = len(stderr) - MAX_RESULT
        out = stdout[:MAX_RESULT] + stderr[tail_start if tail_start > 0 else 0 :]
        output = out.strip()
        if not output:
            output = "(no output)"
        if r.returncode == 0:
            return ActionResult(True, output)
        return ActionResult(False, output, classify_error(output, "shell", command))

    def _write(self, action: ActionEnvelope) -> ActionResult:
        try:
            p = self._resolve(action.text("arg"))
            os.makedirs(path_parent(p), exist_ok=True)
            raw_content = action.fields.get("content", "")
            # Auto-serialize dict/list content — models often output JSON as
            # objects instead of escaped strings.
            if isinstance(raw_content, str):
                content = raw_content
            else:
                content = dumps_pretty(raw_content)
            name = path_name(p)
            if action.flag("append"):
                # Chunked-write transport: append one chunk at a time so large
                # files fit within the executor token budget.
                existed = os.path.exists(p)
                append_text(p, content)
                size = os.path.getsize(p)
                verb = "Appended to" if existed else "Wrote"
                return ActionResult(True, f"{verb} {name} (+{len(content)} chars, total {size})")
            self._atomic_write_text(p, content)
            return ActionResult(True, f"Wrote {name}")
        except Exception as e:
            return self._exception_result(e, "write")

    def _edit(self, action: ActionEnvelope) -> ActionResult:
        try:
            p = self._resolve(action.text("arg"))
            name = path_name(p)
            if not os.path.exists(p):
                return ActionResult(False, f"File not found: {name}", "missing_file")
            text = read_text(p)
            find = action.text("find")
            replace = action.text("replace")
            count = text.count(find)
            if count == 0:
                return ActionResult(False, f"No match for find string in {name}", "edit_failed")
            if count > 1:
                return ActionResult(
                    False,
                    f"Ambiguous: find string matches {count} times in {name}",
                    "edit_failed",
                )
            self._atomic_write_text(p, text.replace(find, replace, 1))
            return ActionResult(True, f"Edited {name}")
        except Exception as e:
            return self._exception_result(e, "edit")

    def _empty_page(
        self,
        ok: bool,
        output: str,
        error_type: str | None,
        meta: dict[str, JSONValue],
    ) -> ActionResult:
        details: dict[str, JSONValue] = {"truncated": False, "content": "", "continuation": None}
        details.update(meta)
        return ActionResult(ok, output, error_type, details)

    def _read(self, action: ActionEnvelope) -> ActionResult:
        try:
            p = self._resolve(action.text("arg"))
            name = path_name(p)
            raw = read_bytes(p)
            text = raw.decode("utf-8")
            lines = text.splitlines(True)
            total = len(lines)
            offset = get_int(action.fields, "offset", 1)
            limit = get_int(action.fields, "limit", READ_LINES)
            # Hash the exact bytes whose decoded text is paged. Continuation
            # cursors count Unicode code points, not UTF-8 bytes or grapheme
            # clusters, and are valid only for this source hash.
            sha = sha256_hex(raw)[:12]
            meta: dict[str, JSONValue] = {
                "total_lines": total,
                "total_bytes": byte_length(raw),
                "total_chars": len(text),
                "sha256": sha,
            }

            has_cursor = action.has("cursor")
            cursor = get_int(action.fields, "cursor", 0)
            expected_hash = action.text("sha256")
            if has_cursor and expected_hash and expected_hash != sha:
                return self._empty_page(
                    False,
                    f"[{name}: stale read cursor; source changed ({expected_hash} -> {sha})]",
                    "stale_read_cursor",
                    meta,
                )
            if not has_cursor and offset > total:
                return self._empty_page(
                    True,
                    f"[{name}: offset {offset} past end of file ({total} lines)]",
                    None,
                    meta,
                )
            if has_cursor and cursor >= len(text):
                return self._empty_page(
                    False,
                    (
                        f"[{name}: read cursor {cursor} must point "
                        f"before end of file ({len(text)} chars)]"
                    ),
                    "invalid_read_cursor",
                    meta,
                )

            starts: list[int] = []
            pos = 0
            for line in lines:
                starts.append(pos)
                pos += len(line)
            if not has_cursor:
                start = starts[offset - 1]
                start_line_index = offset - 1
            else:
                start = cursor
                start_line_index = max(0, bisect.bisect_right(starts, start) - 1)
            window_end_index = min(total, start_line_index + limit)
            window_end = starts[window_end_index] if window_end_index < total else len(text)
            page_cap = READ_CHARS
            body = ""
            output = ""
            has_continuation = False
            continuation: dict[str, JSONValue] = {}
            while True:
                page_end = min(start + page_cap, window_end)
                body = text[start:page_end]
                last_line_index = max(
                    start_line_index,
                    bisect.bisect_right(starts, max(start, page_end - 1)) - 1,
                )
                end = last_line_index + 1
                has_continuation = page_end < len(text)
                header = f"[{name}: lines {start_line_index + 1}-{end} of {total}"
                if page_end < window_end:
                    header += f", cut at {len(body)} chars"
                if has_continuation:
                    next_line_index = max(0, bisect.bisect_right(starts, page_end) - 1)
                    continuation = {
                        "cursor": page_end,
                        "offset": next_line_index + 1,
                        "limit": limit,
                        "sha256": sha,
                    }
                    header += f"; continue: cursor={page_end}, limit={limit}, sha256={sha}"
                header += "]"
                output = f"{header}\n{body}"
                overflow = len(output) - OBSERVE_STATE_CHARS
                if overflow <= 0 or page_cap == 1:
                    break
                page_cap = max(1, page_cap - overflow)
            details: dict[str, JSONValue] = {
                "truncated": has_continuation,
                "content": body,
                "continuation": continuation if has_continuation else None,
            }
            details.update(meta)
            return ActionResult(True, output, None, details)
        except Exception as e:
            return self._exception_result(e, "read")

    def _search(self, action: ActionEnvelope) -> ActionResult:
        pattern = action.text("arg")
        try:
            where = action.text("path")
            base = self._resolve(where if where else ".")
            if not os.path.isdir(base):
                return ActionResult(
                    False, f"Directory not found: {path_name(base)}", "missing_file"
                )
            walk_errors: list[str] = []
            files = _iter_repo_files(base, SEARCH_MAX_FILES + 1, walk_errors)
            file_limited = len(files) > SEARCH_MAX_FILES
            matches: list[str] = []
            snippets_limited = False
            unreadable = 0
            for f in files[:SEARCH_MAX_FILES]:
                try:
                    text = read_text_replace(f)
                except OSError:
                    unreadable += 1
                    continue
                if "\0" in text[:2048]:
                    continue  # skip binary files
                relative = path_relative_to(f, base)
                lineno = 0
                for line in text.splitlines():
                    lineno += 1
                    if pattern in line:
                        snippet = line.strip()
                        if len(snippet) > 100:
                            snippet = snippet[:99] + "…"
                            snippets_limited = True
                        matches.append(f"{relative}:{lineno}: {snippet}")
                        if len(matches) > SEARCH_MAX_MATCHES:
                            break
                if len(matches) > SEARCH_MAX_MATCHES:
                    break
            match_limited = len(matches) > SEARCH_MAX_MATCHES
            shown = matches[:SEARCH_MAX_MATCHES]
            reasons: list[str] = []
            if match_limited:
                reasons.append("matches")
            if file_limited:
                reasons.append("files")
            if snippets_limited:
                reasons.append("snippets")
            if unreadable:
                reasons.append("unreadable")
            if walk_errors:
                reasons.append("walk_errors")

            def search_header(active_reasons: list[str]) -> str:
                marker = ""
                for reason in active_reasons:
                    if reason in ("matches", "files", "chars"):
                        marker = "+"
                header = f"[{len(shown)}{marker} matches for '{pattern[:40]}'"
                if active_reasons:
                    header += (
                        " — incomplete: "
                        + ", ".join(active_reasons)
                        + "; narrow the pattern/path or read the file"
                    )
                return header + "]"

            output, reasons = _pack_observation_lines(
                search_header, shown, reasons, min(SEARCH_MAX_CHARS, OBSERVE_STATE_CHARS)
            )
            details: dict[str, JSONValue] = {
                "truncated": bool(reasons),
                "truncation_reasons": str_items(reasons),
            }
            return ActionResult(True, output, None, details)
        except Exception as e:
            return self._exception_result(e, "search")

    def _tree(self, action: ActionEnvelope) -> ActionResult:
        try:
            where = action.text("arg")
            base = self._resolve(where if where else ".")
            base_name = path_name(base)
            if not os.path.isdir(base):
                return ActionResult(False, f"Directory not found: {base_name}", "missing_file")
            entries: list[str] = []
            depth_limited = False
            walk_errors = 0
            stack: list[tuple[str, int]] = [(base, 0)]
            while stack:
                dirpath, depth = stack.pop()
                dirs, files, readable = list_dir(dirpath)
                if not readable:
                    walk_errors += 1
                    continue
                dirnames = sorted(
                    [d for d in dirs if d not in _REPO_SKIP_DIRS and not d.startswith(".")]
                )
                if depth >= TREE_MAX_DEPTH:
                    if dirnames:
                        depth_limited = True
                    dirnames = []
                rel_dir = path_relative_to(dirpath, base)
                prefix = "" if rel_dir == "." else f"{rel_dir}/"
                for d in dirnames:
                    entries.append(f"{prefix}{d}/")
                for name in sorted(files):
                    if not name.startswith("."):
                        entries.append(f"{prefix}{name}")
                if len(entries) > TREE_MAX_ENTRIES:
                    break
                index = len(dirnames) - 1
                while index >= 0:
                    child = os.path.join(dirpath, dirnames[index])
                    if not os.path.islink(child):
                        stack.append((child, depth + 1))
                    index -= 1
            entry_limited = len(entries) > TREE_MAX_ENTRIES
            shown = entries[:TREE_MAX_ENTRIES]
            reasons: list[str] = []
            if entry_limited:
                reasons.append("entries")
            if depth_limited:
                reasons.append("depth")
            if walk_errors:
                reasons.append("walk_errors")

            def tree_header(active_reasons: list[str]) -> str:
                header = f"[tree of {base_name}: {len(shown)} entries"
                if "entries" in active_reasons:
                    header += f", capped at {TREE_MAX_ENTRIES}"
                if active_reasons:
                    header += " — incomplete: " + ", ".join(active_reasons) + "; narrow the path"
                return header + "]"

            output, reasons = _pack_observation_lines(
                tree_header, shown, reasons, min(TREE_MAX_CHARS, OBSERVE_STATE_CHARS)
            )
            details: dict[str, JSONValue] = {
                "truncated": bool(reasons),
                "truncation_reasons": str_items(reasons),
            }
            return ActionResult(True, output, None, details)
        except Exception as e:
            return self._exception_result(e, "tree")


class SkippedStep:
    """Typed record of a selected action a guard suppressed.

    Skips never dispatch and never enter the model-visible window or the
    run-wide structured record; their one projection is the ``step_skipped``
    JSONL event, produced here so the reason taxonomy has a single owner.
    """

    def __init__(self, task_index: int, step: int, action: str, arg: str, reason: str) -> None:
        self.task_index = task_index
        self.step = step
        self.action = action
        self.arg = arg
        self.reason = reason

    def jsonl_event(self) -> dict[str, JSONValue]:
        event: dict[str, JSONValue] = {
            "event": "step_skipped",
            "task_index": self.task_index,
            "step": self.step,
            "action": self.action,
            "arg": self.arg[:120],
            "reason": self.reason,
        }
        return event


class StepReceipt:
    """Internal record of one recorded step.

    Owns the state entry — the model-visible sliding window and run-wide
    structured record, including underscore-prefixed guard metadata — plus the
    explicit projections for model history and the JSONL run log.
    """

    def __init__(
        self,
        entry: dict[str, JSONValue],
        history_action: dict[str, JSONValue],
        result: ActionResult,
        deterministic: str = "",
        truncated_write: bool = False,
    ) -> None:
        self.entry = entry
        self.history_action = history_action
        self.result = result
        self.deterministic = deterministic  # "" | "repair" | "retry"
        self.truncated_write = truncated_write

    def history_event(self, task_index: int, step: int) -> dict[str, JSONValue]:
        result: dict[str, JSONValue] = {
            "ok": self.entry["ok"],
            "output": get_str(self.entry, "output")[:100],
        }
        event: dict[str, JSONValue] = {
            "event": "step",
            "task": task_index,
            "step": step,
            "action": self.history_action,
            "result": result,
        }
        if self.deterministic == "repair":
            event["deterministic_repair"] = True
        elif self.deterministic == "retry":
            event["deterministic_retry"] = True
        return event

    def jsonl_event(self, task_index: int, step: int, wall_s: float | None) -> dict[str, JSONValue]:
        if self.deterministic == "repair":
            repair: dict[str, JSONValue] = {
                "event": "deterministic_repair",
                "kind": "compile_include",
                "file": self.entry["arg"],
                "description": self.entry["output"],
                "ok": self.entry["ok"],
            }
            return repair
        record: dict[str, JSONValue] = {
            "event": "step",
            "task_index": task_index,
            "step": step,
            "action": self.entry["action"],
            "arg": get_str(self.entry, "arg")[:120],
            "ok": self.entry["ok"],
            "error_type": self.result.error_type,
        }
        if self.deterministic == "retry":
            record["deterministic_retry"] = True
        record["wall_s"] = wall_s
        if truthy(self.result.get("truncated")):
            record["truncated"] = True
        # Bounded discovery is only auditable when the record says why it
        # stopped: keep the compact cap reasons.
        if truthy(self.result.get("truncation_reasons")):
            record["truncation_reasons"] = self.result.get("truncation_reasons")
        if self.truncated_write:
            record["truncated_write"] = True
        # Hash-linked read audit: which content, how much of it, and where the
        # window ended.
        if self.entry["action"] == "read" and truthy(self.result.get("sha256")):
            record["sha256"] = self.result.get("sha256")
            record["total_lines"] = self.result.get("total_lines")
            record["total_bytes"] = self.result.get("total_bytes")
            record["total_chars"] = self.result.get("total_chars")
            record["continuation"] = self.result.get("continuation")
        return record


def receipt_executed(
    action: ActionEnvelope, result: ActionResult, working_dir: str, truncated_write: bool = False
) -> StepReceipt:
    """Receipt for a model action that reached the dispatcher."""
    act = action.name
    # Truncated-write outputs carry the resume anchor the next step navigates
    # by — observation-class budget, not 100.
    out_cap = OBSERVE_STATE_CHARS if act in OBSERVE_ACTIONS or truncated_write else 100
    entry: dict[str, JSONValue] = {
        "action": act,
        "arg": action.text("arg"),
        "ok": result.ok,
        "output": result.output[:out_cap],
    }
    if not result.ok and result.error_type is not None:
        entry["error_type"] = result.error_type
    if act == "shell" and action.has("timeout"):
        entry["_timeout"] = action.fields["timeout"]
    if act == "write":
        entry["_content"] = json_copy(action.fields.get("content", ""))
        if action.flag("append"):
            entry["_append"] = True
        if truncated_write:
            entry["_truncated_write"] = True
    if act == "edit":
        entry["_find"] = action.text("find")
        entry["_replace"] = action.text("replace")
    if act in ("write", "edit"):
        target_step: dict[str, JSONValue] = {"arg": action.text("arg")}
        if act == "write" and action.flag("append"):
            target_step["append"] = True
        target = _mutation_target_key(target_step, working_dir)
        if target is not None:
            entry["_target"] = target
            if act == "write" and truncated_write:
                entry["_recovery_arg"] = _target_recovery_arg(target, working_dir)
    if act == "read":
        entry["_read_key"] = _read_key(action.fields)
        continuation = result.get("continuation")
        if truthy(continuation):
            entry["_continuation"] = continuation
    return StepReceipt(entry, action.to_dict(), result, "", truncated_write)


def receipt_deterministic_repair(action: dict[str, JSONValue], result: ActionResult) -> StepReceipt:
    """Receipt for the compile-repair rule's dispatched action.

    The rule proposes a normal action and the controller dispatches it through
    the action executor, so ``ok`` reflects the real dispatch result. A
    successful receipt keeps the human description (the action's
    ``reasoning``) that downstream task matching reads; a refused dispatch
    keeps its actionable error output instead."""
    if result.ok:
        output = get_str(action, "reasoning")
        if not output:
            output = result.output[:100]
    else:
        output = result.output[:100]
    entry: dict[str, JSONValue] = {
        "action": get_str(action, "action"),
        "arg": get_str(action, "arg"),
        "ok": result.ok,
        "output": output,
        "deterministic_repair": True,
    }
    # No model action produced this step: history shows the entry itself.
    return StepReceipt(entry, entry, result, "repair")


def receipt_deterministic_retry(action: ActionEnvelope, result: ActionResult) -> StepReceipt:
    """Receipt for the scaffold-initiated shell retry after a repair."""
    entry: dict[str, JSONValue] = {
        "action": "shell",
        "arg": action.text("arg"),
        "ok": result.ok,
        "output": result.output[:100],
        "deterministic_retry": True,
    }
    if not result.ok and result.error_type is not None:
        entry["error_type"] = result.error_type
    history_action: dict[str, JSONValue] = {"action": "shell", "arg": action.text("arg")}
    return StepReceipt(entry, history_action, result, "retry")
